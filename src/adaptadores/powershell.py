"""Adaptador del motor `powershell`: ejecuta la plantilla del catálogo en Windows (regla 11).

Es, junto con `comando.py`, el único módulo del proyecto que importa `subprocess`. PowerShell se
lanza con `-NoProfile -NonInteractive` y, en Windows, sin ventana (`CREATE_NO_WINDOW`).
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

from src import catalogo
from src.adaptadores.base import Invocacion, SalidaAdaptador

MOTOR = "powershell"

BINARIO = "powershell.exe"
OPCIONES = ("-NoProfile", "-NonInteractive", "-Command")

# Bandera de Win32 que evita abrir una consola visible; fuera de Windows no existe en subprocess.
CREATE_NO_WINDOW: int = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)

# Codificación con la que PowerShell escribe su salida al estar redirigida: la página de códigos OEM
# de la consola (cp850 en un Windows en español), no la ANSI (cp1252) que Python usaría por defecto.
# Sin esto, «ó», «á» e «í» llegan como «¢», un espacio duro y «¡» (INC-10).
CODIFICACION_SALIDA = "oem" if sys.platform == "win32" else "utf-8"

_TOOLS_LISTA = {
    "get_detected_threats",
    "get_active_network_profile",
    "get_allowed_firewall_rules",
    "get_bitlocker_status",
    "get_storage_status",
}


def _normalizar_datos_lista(tool_id: str, datos: Any) -> Any:
    """Normaliza salidas de ConvertTo-Json que semánticamente son listas.

    ConvertTo-Json produce null/vacío para 0 elementos y un objeto suelto (no un
    array) para exactamente 1 elemento. Solo las herramientas de _TOOLS_LISTA
    devuelven una cantidad variable de elementos (0, 1 o varios), así que solo a
    esas se les aplica esta normalización.
    """
    if tool_id not in _TOOLS_LISTA:
        return datos
    if datos is None:
        return []
    if isinstance(datos, dict):
        return [datos]
    return datos


def construir(entrada: catalogo.Entrada, params: dict[str, str]) -> Invocacion:
    """Formatea la plantilla con los valores ya validados y prepara la línea de PowerShell."""
    plantilla = entrada.plantilla or ""
    texto = plantilla.format(**params) if entrada.parametros else plantilla
    return Invocacion(
        tool_id=entrada.id,
        motor=MOTOR,
        texto=texto,
        timeout_s=entrada.timeout_s,
        argv=(BINARIO, *OPCIONES, texto),
    )


def _opciones_ventana() -> dict[str, int]:
    """En Windows, pide a subprocess que no abra ninguna ventana de consola."""
    return {"creationflags": CREATE_NO_WINDOW} if sys.platform == "win32" else {}


def ejecutar(invocacion: Invocacion) -> SalidaAdaptador:
    """Lanza PowerShell, interpreta su salida JSON y normaliza los errores."""
    tool_id = invocacion.tool_id
    try:
        proceso = subprocess.run(
            list(invocacion.argv),
            capture_output=True,
            encoding=CODIFICACION_SALIDA,
            errors="replace",
            timeout=invocacion.timeout_s,
            **_opciones_ventana(),
        )
    except FileNotFoundError:
        return SalidaAdaptador(
            estado="no_aplicable",
            error="No se ha encontrado powershell.exe. Este equipo requiere Windows con PowerShell en el PATH.",
        )
    except subprocess.TimeoutExpired:
        return SalidaAdaptador(
            estado="error",
            error=f"El comando ha tardado más de {invocacion.timeout_s} segundos y se ha cancelado.",
        )

    if proceso.returncode != 0:
        error_ps = proceso.stderr.strip() or "sin detalles adicionales"
        return SalidaAdaptador(
            estado="error", error=f"PowerShell devolvió un error al ejecutar '{tool_id}' ({error_ps})."
        )

    salida = proceso.stdout.strip()
    try:
        datos = json.loads(salida) if salida else None
    except json.JSONDecodeError:
        return SalidaAdaptador(
            estado="error", error=f"La salida de PowerShell para '{tool_id}' no es un JSON válido: {salida!r}"
        )
    return SalidaAdaptador(estado="ok", datos=_normalizar_datos_lista(tool_id, datos))
