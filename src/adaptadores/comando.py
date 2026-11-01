"""Adaptador del motor `comando`: ejecuta un binario con argv en lista, sin shell (regla 10).

El binario se resuelve a ruta absoluta con `shutil.which` sobre un PATH fijo, el proceso hereda
solo un entorno mínimo (`ENTORNO_FIJO`) y siempre lleva timeout. Cada elemento de argv se
formatea por separado con los valores validados: un valor nunca se mezcla con otro elemento, y
argv nunca se une en una cadena para ejecutarlo. En H1 este motor solo se admite en Linux
(ver `docs/memoria/CAMBIOS.md`).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import PurePosixPath

from src import catalogo
from src.adaptadores.base import Invocacion, SalidaAdaptador
from src.plataforma import deteccion

MOTOR = "comando"

# El mismo PATH con el que la detección resuelve los binarios: la ruta detectada es la que se ejecuta.
PATH_FIJO = deteccion.PATH_LINUX_FIJO
ENTORNO_FIJO: dict[str, str] = {"LC_ALL": "C", "PATH": PATH_FIJO}


def construir(entrada: catalogo.Entrada, params: dict[str, str]) -> Invocacion:
    """Sustituye los parámetros elemento a elemento de argv (nunca sobre argv unido)."""
    argv = tuple(a.format(**params) for a in entrada.argv or ()) if entrada.parametros else tuple(entrada.argv or ())
    return Invocacion(
        tool_id=entrada.id,
        motor=MOTOR,
        texto=" ".join(argv),  # solo para mostrar y auditar
        timeout_s=entrada.timeout_s,
        argv=argv,
    )


def resolver_binario(nombre: str) -> str | None:
    """Ruta absoluta del binario en PATH_FIJO, o None si no está o no es absoluta."""
    ruta = shutil.which(nombre, path=PATH_FIJO)
    return ruta if ruta and PurePosixPath(ruta).is_absolute() else None


def ejecutar(invocacion: Invocacion) -> SalidaAdaptador:
    """Ejecuta el binario resuelto con `shell=False`, entorno fijo y timeout."""
    if not invocacion.argv:
        return SalidaAdaptador(estado="error", error=f"'{invocacion.tool_id}' no tiene argv.")
    binario = invocacion.argv[0]
    ruta = resolver_binario(binario)
    if ruta is None:
        return SalidaAdaptador(estado="no_aplicable", error=f"No se ha encontrado el binario '{binario}' en este equipo.")
    try:
        proceso = subprocess.run(
            [ruta, *invocacion.argv[1:]],
            shell=False,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=invocacion.timeout_s,
            env=dict(ENTORNO_FIJO),
        )
    except FileNotFoundError:
        return SalidaAdaptador(estado="no_aplicable", error=f"No se ha encontrado el binario '{binario}' en este equipo.")
    except subprocess.TimeoutExpired:
        return SalidaAdaptador(
            estado="error",
            error=f"El comando ha tardado más de {invocacion.timeout_s} segundos y se ha cancelado.",
        )
    if proceso.returncode != 0:
        detalle = proceso.stderr.strip() or "sin detalles adicionales"
        return SalidaAdaptador(
            estado="error",
            error=f"'{binario}' devolvió el código {proceso.returncode} al ejecutar '{invocacion.tool_id}' ({detalle}).",
        )
    return SalidaAdaptador(estado="ok", datos=proceso.stdout.strip())
