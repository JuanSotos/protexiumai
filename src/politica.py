"""Política en tiempo de ejecución: decide, en cada llamada y antes de tocar nada, si se permite.

El cargador del catálogo (`src/catalogo.py`) valida las entradas una vez, al arrancar. Esta
política vuelve a comprobarlas en cada llamada, justo antes de ejecutar: si el catálogo en memoria
se hubiera alterado después de cargarlo, la llamada se rechaza igualmente. Se evalúa en dos
momentos:

1. `evaluar_llamada`: la herramienta existe, su motor es coherente, aplica a este equipo y perfil,
   y los parámetros son exactamente los declarados y con valores de su enum.
2. `evaluar_invocacion`: lo ya construido por el adaptador (texto de PowerShell, argv o clave de
   registro) no contiene tokens de la lista de denegación, binarios de elevación ni hives
   desconocidos.

Este módulo no ejecuta nada ni escribe en ningún sitio: devuelve una `Decision` y el executor la
audita y actúa.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from typing import TYPE_CHECKING, Any, Literal

from src import catalogo
from src.adaptadores import ADAPTADORES
from src.adaptadores.base import Invocacion
from src.adaptadores.registro import HIVES

if TYPE_CHECKING:
    from src.plataforma.deteccion import Capacidades

ResultadoDecision = Literal["permitida", "rechazada", "no_aplicable"]

# Motivos de rechazo que se auditan en `motivo_rechazo` (además de los ya existentes).
MOTIVO_DESCONOCIDO = "tool_id_desconocido"
MOTIVO_MOTOR_RESERVADO = "motor_reservado"
MOTIVO_MOTOR_NO_SOPORTADO = "motor_no_soportado"
MOTIVO_NO_APLICABLE = "no_aplicable"
MOTIVO_NO_DECLARADO = "parametro_no_declarado"
MOTIVO_FALTANTE = "parametro_faltante"
MOTIVO_FUERA_DE_ENUM = "valor_fuera_de_enum"
MOTIVO_DENEGADO = "denegado_por_politica"
MOTIVO_HIVE = "hive_desconocido"

# Sistemas en los que puede ejecutarse cada motor. `comando` solo en Linux en H1 (regla 10; en
# Windows rige la regla 11: PowerShell y winreg). `python` está reservado.
MOTORES_POR_SO: dict[str, frozenset[str]] = {
    "powershell": frozenset({"windows"}),
    "registro": frozenset({"windows"}),
    "comando": frozenset({"linux"}),
}

# Binarios de elevación de privilegios: nunca se ejecutan, aparezcan donde aparezcan en argv (regla 10).
BINARIOS_PROHIBIDOS = frozenset({"sudo", "su", "pkexec", "doas"})


@dataclass(frozen=True)
class Decision:
    """Resultado de la política: si la llamada sigue adelante y, si no, por qué."""

    resultado: ResultadoDecision
    motivo: str | None = None
    mensaje: str = ""

    @property
    def permitida(self) -> bool:
        """True si la llamada puede continuar."""
        return self.resultado == "permitida"

    @property
    def estado(self) -> str:
        """Estado normalizado del resultado (regla 14) que corresponde a la decisión."""
        return "no_aplicable" if self.resultado == "no_aplicable" else "error"


PERMITIDA = Decision("permitida")


def _rechazo(motivo: str, mensaje: str) -> Decision:
    return Decision("rechazada", motivo, mensaje)


# --- Primer momento: la llamada ----------------------------------------------------------
def _comprobar_motor(entrada: catalogo.Entrada) -> Decision:
    """El motor debe tener adaptador y ser coherente con el sistema que declara la entrada."""
    if entrada.motor == "python":
        return _rechazo(
            MOTIVO_MOTOR_RESERVADO,
            f"'{entrada.id}' usa el motor 'python', reservado y sin uso en esta versión.",
        )
    sistemas = MOTORES_POR_SO.get(entrada.motor)
    if sistemas is None or entrada.motor not in ADAPTADORES:
        return _rechazo(MOTIVO_MOTOR_NO_SOPORTADO, f"'{entrada.id}' usa un motor no soportado: '{entrada.motor}'.")
    if entrada.plataforma.so not in sistemas:
        return _rechazo(
            MOTIVO_MOTOR_NO_SOPORTADO,
            f"'{entrada.id}': el motor '{entrada.motor}' no se admite en {entrada.plataforma.so}.",
        )
    return PERMITIDA


def _comprobar_parametros(tool_id: str, entrada: catalogo.Entrada, params: dict[str, Any]) -> Decision:
    """Ni de más, ni de menos, ni fuera del enum cerrado (mismos mensajes que antes de P11)."""
    claves_recibidas = set(params.keys())
    claves_declaradas = set(entrada.parametros.keys())

    no_declaradas = claves_recibidas - claves_declaradas
    if no_declaradas:
        return _rechazo(
            MOTIVO_NO_DECLARADO,
            f"Parámetro(s) no declarado(s) para '{tool_id}': {sorted(no_declaradas)}.",
        )

    faltantes = claves_declaradas - claves_recibidas
    if faltantes:
        return _rechazo(
            MOTIVO_FALTANTE,
            f"Falta(n) parámetro(s) obligatorio(s) para '{tool_id}': {sorted(faltantes)}.",
        )

    for nombre, valor in params.items():
        permitidos = list(entrada.parametros[nombre])
        if valor not in permitidos:
            return _rechazo(
                MOTIVO_FUERA_DE_ENUM,
                f"Valor '{valor}' no permitido para '{nombre}' (permitidos: {permitidos}).",
            )
    return PERMITIDA


def evaluar_llamada(
    tool_id: str,
    entrada: catalogo.Entrada | None,
    params: dict[str, Any],
    capacidades: Capacidades,
    perfil: str,
) -> Decision:
    """Decide si la llamada puede construirse: id, motor, aplicabilidad y parámetros, por ese orden."""
    if entrada is None:
        return _rechazo(MOTIVO_DESCONOCIDO, f"Herramienta desconocida: '{tool_id}'.")

    decision = _comprobar_motor(entrada)
    if not decision.permitida:
        return decision

    aplica, motivo = catalogo.aplicable(entrada, capacidades, perfil)
    if not aplica:
        return Decision("no_aplicable", MOTIVO_NO_APLICABLE, f"'{tool_id}' no aplica a este equipo: {motivo}.")

    return _comprobar_parametros(tool_id, entrada, params)


# --- Segundo momento: la invocación construida -------------------------------------------
def _nombre_base(elemento: str) -> str:
    """Último componente de una ruta, en minúsculas, valga como ruta POSIX o de Windows."""
    return PureWindowsPath(PurePosixPath(elemento).name).name.lower()


def evaluar_invocacion(invocacion: Invocacion) -> Decision:
    """Comprueba lo que se va a ejecutar: lista de denegación, binarios de elevación y hives."""
    if invocacion.motor == "registro":
        clave = invocacion.clave
        if clave is None or clave.hive not in HIVES:
            hive = clave.hive if clave is not None else None
            return _rechazo(MOTIVO_HIVE, f"'{invocacion.tool_id}': hive de registro no permitido: {hive!r}.")
        candidatos: tuple[str, ...] = (clave.ruta, clave.valor)
    elif invocacion.motor == "comando":
        for elemento in invocacion.argv:
            if _nombre_base(elemento) in BINARIOS_PROHIBIDOS:
                return _rechazo(
                    MOTIVO_DENEGADO,
                    f"'{invocacion.tool_id}' intenta usar '{elemento}': la elevación de privilegios está prohibida.",
                )
        candidatos = (*invocacion.argv, " ".join(invocacion.argv))
    else:
        candidatos = (invocacion.texto,)

    for candidato in candidatos:
        if (token := catalogo.buscar_token_denegado(candidato)) is not None:
            return _rechazo(
                MOTIVO_DENEGADO,
                f"'{invocacion.tool_id}' contiene el token denegado '{token}': ejecución bloqueada por la política.",
            )
    return PERMITIDA
