"""Lectura y traducción a llano del registro de auditoría (`logs/audit.jsonl`).

Módulo de solo lectura: `src/audit.py` es quien escribe, y aquí no se toca. Cada
línea del registro se convierte en una fila con el nombre en llano de la
herramienta, el desenlace (o el motivo de rechazo del ADDENDUM-02 §3), quién lo
autorizó y en qué proveedor se resolvió el turno (§11).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app import textos
from src import audit, executor

# Marca previa que escribe executor.execute antes de ejecutar una accion/mutante:
# la línea existe para demostrar que la auditoría se registra ANTES de tocar
# PowerShell, y se funde con la línea definitiva de la misma llamada.
MARCA_PREVIA = "en curso"

MARCA_HECHA = "✓"
MARCA_SIN_HACER = "—"

NOTA_REGISTRO = "El registro se guarda en tu equipo, en formato de texto, y no se envía a ningún sitio."


@dataclass(frozen=True)
class Entrada:
    """Una llamada al executor, ya traducida para la pantalla de auditoría."""

    hora: str
    marca: str
    titulo: str
    resultado: str
    autor: str
    proveedor: str
    hecha: bool
    detalle: list[tuple[str, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Diagnóstico de los errores de ejecución (§5)
# ---------------------------------------------------------------------------

_PATRONES_ERROR: tuple[tuple[str, str], ...] = (
    ("no se ha encontrado powershell", "powershell_no_encontrado"),
    ("ha tardado más de", "timeout"),
    ("no es un json válido", "salida_ilegible"),
    ("requiere privilegios de administrador", "requiere_elevacion"),
    ("powershell devolvió un error", "error_powershell"),
)


def clasificar_error(mensaje: str | None) -> str | None:
    """Caso del §5 al que corresponde un error del executor, o None si no encaja."""
    if not mensaje:
        return None
    texto = mensaje.lower()
    for patron, caso in _PATRONES_ERROR:
        if patron in texto:
            return caso
    return None


def es_tiempo_agotado(mensaje: str | None) -> bool:
    """True si el error del executor es el vencimiento de su propio timeout."""
    return clasificar_error(mensaje) == "timeout"


# ---------------------------------------------------------------------------
# Lectura del archivo
# ---------------------------------------------------------------------------

def _momento(iso: Any) -> datetime | None:
    try:
        momento = datetime.fromisoformat(str(iso))
    except (TypeError, ValueError):
        return None
    if momento.tzinfo is None:
        momento = momento.replace(tzinfo=timezone.utc)
    return momento.astimezone()


def leer_registro(desde: datetime | None = None, maximo: int = 500) -> list[dict[str, Any]]:
    """Lee el JSONL y funde las dos líneas (previa y definitiva) de cada llamada.

    `desde` acota el registro a la sesión en curso; las líneas anteriores siguen
    en el archivo, no se borran ni se reescriben nunca.
    """
    ruta = audit.RUTA_LOG
    if not ruta.exists():
        return []
    with ruta.open(encoding="utf-8") as f:
        lineas = f.readlines()[-maximo:]

    fundidas: dict[tuple[str, str], dict[str, Any]] = {}
    orden: list[tuple[str, str]] = []
    for linea in lineas:
        linea = linea.strip()
        if not linea:
            continue
        try:
            entrada = json.loads(linea)
        except json.JSONDecodeError:
            continue
        momento = _momento(entrada.get("timestamp"))
        if desde is not None and (momento is None or momento < desde):
            continue
        clave = (str(entrada.get("timestamp")), str(entrada.get("tool_id")))
        if clave not in fundidas:
            orden.append(clave)
            entrada["lineas"] = 1
        else:
            entrada["lineas"] = fundidas[clave].get("lineas", 1) + 1
        fundidas[clave] = entrada
    return [fundidas[c] for c in orden]


# ---------------------------------------------------------------------------
# Traducción de una entrada
# ---------------------------------------------------------------------------

_ETIQUETA_PARAMETRO = {
    "profile": "perfil",
    "enabled": "activar",
    "allow_inbound_rules": "permitir entrantes",
    "ruta": "carpeta",
    "_argumentos_crudos": "argumentos recibidos",
}


def _parametros_legibles(params: dict[str, Any]) -> str:
    if not params:
        return "ninguno"
    return " · ".join(f"{_ETIQUETA_PARAMETRO.get(k, k)} = {v}" for k, v in params.items())


def _duracion(resultado: dict[str, Any]) -> str:
    try:
        segundos = float(resultado.get("duracion_s", 0))
    except (TypeError, ValueError):
        return "Hecho"
    return f"Hecho en {segundos:.1f} s".replace(".", ",")


def _autor(tool_id: str, motivo: str | None, hecha: bool) -> str:
    spec = executor.WHITELIST.get(tool_id)
    if motivo == "usuario_rechazo":
        return textos.AUTOR_RECHAZADO
    if motivo is not None:
        return textos.AUTOR_SISTEMA
    if spec is not None and spec.nivel == "lectura":
        return textos.AUTOR_SIN_PERMISO
    if hecha:
        return textos.AUTOR_AUTORIZADO
    return textos.AUTOR_SISTEMA


def traducir(entrada: dict[str, Any]) -> Entrada:
    """Convierte una línea del registro en la fila que se muestra en pantalla."""
    tool_id = str(entrada.get("tool_id", ""))
    params = entrada.get("params") or {}
    resultado = entrada.get("resultado") or {}
    motivo = entrada.get("motivo_rechazo")
    proveedor = entrada.get("proveedor")
    hecha = bool(resultado.get("ok"))

    momento = _momento(entrada.get("timestamp"))
    hora = f"{momento:%H:%M:%S}" if momento else "--:--:--"

    if hecha:
        desenlace = _duracion(resultado)
    elif motivo:
        desenlace = textos.MOTIVO_RECHAZO.get(str(motivo), textos.MOTIVO_DESCONOCIDO)
    else:
        caso = clasificar_error(resultado.get("error"))
        desenlace = (
            f"Sin hacer · {textos.ERRORES_SISTEMA[caso][0].lower()}" if caso else textos.MOTIVO_DESCONOCIDO
        )

    detalle: list[tuple[str, str]] = [
        ("Herramienta", tool_id),
        ("Parámetros", _parametros_legibles(params)),
        ("Comando", str(resultado.get("comando") or "no se llegó a construir")),
        ("Resultado", "correcto" if hecha else str(resultado.get("error") or desenlace)),
        ("Proveedor", textos.PROVEEDOR_AUDITORIA.get(str(proveedor), "sin proveedor")),
    ]
    if entrada.get("lineas", 1) > 1:
        detalle.append(("Registro", "se anotó antes de ejecutarse y otra vez al terminar"))

    return Entrada(
        hora=hora,
        marca=MARCA_HECHA if hecha else MARCA_SIN_HACER,
        titulo=textos.frase(tool_id, params, "hecho" if hecha else "sin_hacer"),
        resultado=desenlace,
        autor=_autor(tool_id, str(motivo) if motivo else None, hecha),
        proveedor=textos.PROVEEDOR_AUDITORIA.get(str(proveedor), "—"),
        hecha=hecha,
        detalle=detalle,
    )


def entradas(desde: datetime | None = None, solo_sin_hacer: bool = False) -> list[Entrada]:
    """Las entradas del registro, de la más reciente a la más antigua."""
    traducidas = [traducir(e) for e in leer_registro(desde)]
    traducidas.reverse()
    if solo_sin_hacer:
        return [e for e in traducidas if not e.hecha]
    return traducidas


def recuento(lista: list[Entrada]) -> tuple[int, int, int]:
    """(total, hechas, sin hacer) para la línea de resumen de la cabecera."""
    hechas = sum(1 for e in lista if e.hecha)
    return len(lista), hechas, len(lista) - hechas
