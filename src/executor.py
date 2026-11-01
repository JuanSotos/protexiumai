"""Capa ejecutora: WHITELIST derivada del catálogo YAML, política en cada llamada, privilegios, auditoría y despacho al adaptador de cada motor.

Este módulo no ejecuta nada por sí mismo ni importa `subprocess` (regla 1): orquesta. Para cada
llamada aplica la política (`src/politica.py`), comprueba privilegios sin elevar, audita y delega
la ejecución en el adaptador del motor de la herramienta (`src/adaptadores/`).
"""

from __future__ import annotations

import ctypes
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from src import adaptadores, audit, catalogo, politica
from src.adaptadores import powershell
from src.plataforma import deteccion

# Motores que el executor sabe ejecutar: los que tienen adaptador. `python` está reservado.
MOTORES_EJECUTABLES = tuple(adaptadores.ADAPTADORES)


@dataclass(frozen=True)
class ToolSpec:
    """Especificación de una herramienta permitida en la WHITELIST (vista derivada del catálogo)."""

    id: str
    descripcion: str
    plantilla: str | None
    parametros: dict[str, list[str]] = field(default_factory=dict)
    nivel: Literal["lectura", "accion", "mutante"] = "lectura"
    requiere_admin: bool = False
    timeout_s: int = 30
    motor: str = "powershell"


def construir_whitelist(cat: catalogo.Catalogo) -> dict[str, ToolSpec]:
    """Deriva la WHITELIST del catálogo: una ToolSpec por herramienta expuesta al LLM.

    Una herramienta con un motor sin adaptador (hoy, `python`) se rechaza al arrancar en lugar de
    ignorarse en silencio.
    """
    whitelist: dict[str, ToolSpec] = {}
    for entrada in cat.herramientas_llm().values():
        if entrada.motor not in MOTORES_EJECUTABLES:
            raise catalogo.CatalogoError(
                f"{entrada.origen}: entrada '{entrada.id}': el executor solo ejecuta herramientas "
                "con motor 'powershell', 'registro' o 'comando'."
            )
        whitelist[entrada.id] = ToolSpec(
            id=entrada.id,
            descripcion=entrada.descripcion_llm,
            plantilla=entrada.plantilla,
            parametros={nombre: list(valores) for nombre, valores in entrada.parametros.items()},
            nivel=entrada.nivel,  # type: ignore[arg-type]  (validado por el cargador)
            requiere_admin=entrada.requisitos.privilegios in ("admin", "root"),
            timeout_s=entrada.timeout_s,
            motor=entrada.motor,
        )
    return whitelist


# Catálogo cargado (catalogo/, única fuente de verdad) y su vista derivada. Si el catálogo no
# valida, la importación falla: nunca se ejecuta con una WHITELIST a medias. La política consulta
# CATALOGO en cada llamada, así que una alteración posterior en memoria también se detecta.
CATALOGO: catalogo.Catalogo = catalogo.cargar_catalogo()
WHITELIST: dict[str, ToolSpec] = construir_whitelist(CATALOGO)

# Perfil activo para decidir la aplicabilidad. Hasta que exista la selección de perfil, el de
# por defecto (`hogar`), el mismo con el que se genera el esquema del LLM.
PERFIL_ACTIVO: str = catalogo.PERFIL_POR_DEFECTO

# Se conserva aquí por compatibilidad: la decodificación de la salida vive en el adaptador.
CODIFICACION_SALIDA = powershell.CODIFICACION_SALIDA


def _es_administrador() -> bool:
    """Comprueba si el proceso actual se ejecuta con privilegios de administrador en Windows."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def _capacidades() -> deteccion.Capacidades:
    """Capacidades de este equipo (detectadas una sola vez, en solo lectura)."""
    return deteccion.capacidades_del_equipo()


def _tiene_privilegios(entrada: catalogo.Entrada, capacidades: deteccion.Capacidades) -> bool:
    """True si la entrada no exige privilegios o el proceso ya los tiene. Nunca intenta elevar."""
    privilegios = entrada.requisitos.privilegios
    if privilegios == "admin":
        return _es_administrador()
    if privilegios == "root":
        return capacidades.es_root
    return True


def _construir_resultado(
    *,
    ok: bool,
    tool_id: str,
    comando: str | None,
    timestamp: str,
    duracion_s: float,
    estado: str,
    data: Any = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Construye el dict de resultado con la forma común a éxitos y rechazos."""
    resultado: dict[str, Any] = {
        "ok": ok,
        "estado": estado,
        "tool_id": tool_id,
        "comando": comando,
        "timestamp": timestamp,
        "duracion_s": round(duracion_s, 3),
    }
    resultado["data" if ok else "error"] = data if ok else error
    return resultado


def _auditar(
    *,
    tool_id: str,
    params: dict[str, Any],
    resultado: dict[str, Any],
    motivo_rechazo: str | None,
    estricto: bool,
    proveedor: str | None = None,
) -> None:
    """Registra la auditoría de una llamada.

    Si estricto=False (lectura y rechazos que nunca llegaron al adaptador), un
    fallo al escribir el log solo se avisa por stderr. Si estricto=True
    (herramientas accion/mutante a punto de ejecutarse), el fallo se propaga
    para que execute() aborte antes de invocar al adaptador: ninguna acción o
    mutación se ejecuta si no puede quedar registrada.
    """
    try:
        audit.registrar_auditoria(
            tool_id=tool_id,
            params=params,
            resultado=resultado,
            motivo_rechazo=motivo_rechazo,
            proveedor=proveedor,
        )
    except OSError as error:
        if estricto:
            raise
        print(
            f"Aviso: no se ha podido escribir en el log de auditoría: {error}",
            file=sys.stderr,
        )


def execute(tool_id: str, params: dict[str, Any], *, proveedor: str | None = None) -> dict[str, Any]:
    """Ejecuta de forma segura una herramienta del catálogo y audita la llamada.

    Flujo: política sobre la llamada → construcción por el adaptador → política sobre lo
    construido → privilegios (sin elevar) → auditoría estricta previa (accion/mutante) →
    ejecución por el adaptador → auditoría del resultado.
    """
    inicio = time.monotonic()
    marca_tiempo = datetime.now(timezone.utc).isoformat()

    def _resultado(*, estado: str, comando: str | None, data: Any = None, error: str | None = None) -> dict[str, Any]:
        return _construir_resultado(
            ok=estado == "ok",
            tool_id=tool_id,
            comando=comando,
            timestamp=marca_tiempo,
            duracion_s=time.monotonic() - inicio,
            estado=estado,
            data=data,
            error=error,
        )

    def _rechazar(mensaje: str, motivo: str, estado: str = "error", comando: str | None = None) -> dict[str, Any]:
        resultado = _resultado(estado=estado, comando=comando, error=mensaje)
        _auditar(
            tool_id=tool_id,
            params=params,
            resultado=resultado,
            motivo_rechazo=motivo,
            estricto=False,
            proveedor=proveedor,
        )
        return resultado

    # 1) política sobre la llamada: id, motor, aplicabilidad y parámetros
    capacidades = _capacidades()
    entrada = CATALOGO.herramientas_llm().get(tool_id)
    decision = politica.evaluar_llamada(tool_id, entrada, params, capacidades, PERFIL_ACTIVO)
    if not decision.permitida or entrada is None:
        return _rechazar(decision.mensaje, decision.motivo or politica.MOTIVO_DESCONOCIDO, decision.estado)

    # 2) construir la invocación SOLO a partir de la plantilla/argv/clave del catálogo + valores
    #    validados, y volver a pasar la política sobre lo construido (lista de denegación)
    adaptador = adaptadores.adaptador_para(entrada.motor)
    invocacion = adaptador.construir(entrada, params)
    decision = politica.evaluar_invocacion(invocacion)
    if not decision.permitida:
        return _rechazar(decision.mensaje, decision.motivo or politica.MOTIVO_DENEGADO, comando=invocacion.texto)

    # 3) comprobación de privilegios (sin intento de elevación)
    if not _tiene_privilegios(entrada, capacidades):
        quien = "de root" if entrada.requisitos.privilegios == "root" else "de administrador"
        return _rechazar(
            f"'{tool_id}' requiere privilegios {quien}. "
            "Ejecuta el proceso en una terminal elevada; ProtexiumAI no eleva permisos automáticamente.",
            "requiere_admin",
            estado="requiere_privilegios",
            comando=invocacion.texto,
        )

    # 4) auditoría estricta previa para accion/mutante: si no se puede registrar,
    #    se aborta antes de llegar al adaptador.
    if entrada.nivel != "lectura":
        intento = _resultado(estado="error", comando=invocacion.texto, error="en curso")
        try:
            _auditar(
                tool_id=tool_id,
                params=params,
                resultado=intento,
                motivo_rechazo=None,
                estricto=True,
                proveedor=proveedor,
            )
        except OSError as error:
            return _resultado(
                estado="error",
                comando=invocacion.texto,
                error=(
                    f"No se ha podido registrar la auditoría antes de ejecutar "
                    f"'{tool_id}'; ejecución abortada por seguridad ({error})."
                ),
            )

    # 5) ejecución por el adaptador del motor y auditoría del resultado
    salida = adaptador.ejecutar(invocacion)
    resultado = _resultado(estado=salida.estado, comando=invocacion.texto, data=salida.datos, error=salida.error)
    _auditar(tool_id=tool_id, params=params, resultado=resultado, motivo_rechazo=None, estricto=False, proveedor=proveedor)
    return resultado
