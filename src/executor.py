"""Capa ejecutora: WHITELIST de cmdlets de PowerShell (derivada del catálogo YAML), validación de parámetros, niveles de acción y ejecución segura."""

from __future__ import annotations

import ctypes
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from src import audit, catalogo


@dataclass(frozen=True)
class ToolSpec:
    """Especificación de una herramienta PowerShell permitida en la WHITELIST."""

    id: str
    descripcion: str
    plantilla: str
    parametros: dict[str, list[str]] = field(default_factory=dict)
    nivel: Literal["lectura", "accion", "mutante"] = "lectura"
    requiere_admin: bool = False
    timeout_s: int = 30


def construir_whitelist(cat: catalogo.Catalogo) -> dict[str, ToolSpec]:
    """Deriva la WHITELIST del catálogo: una ToolSpec por herramienta expuesta al LLM.

    El executor solo sabe ejecutar PowerShell en Windows; una herramienta con otro motor u
    otro sistema se rechaza al arrancar en lugar de ignorarse en silencio.
    """
    whitelist: dict[str, ToolSpec] = {}
    for entrada in cat.herramientas_llm().values():
        if entrada.motor != "powershell" or entrada.plataforma.so != "windows" or entrada.plantilla is None:
            raise catalogo.CatalogoError(
                f"{entrada.origen}: entrada '{entrada.id}': el executor solo ejecuta herramientas "
                "con motor 'powershell' en Windows."
            )
        whitelist[entrada.id] = ToolSpec(
            id=entrada.id,
            descripcion=entrada.descripcion_llm,
            plantilla=entrada.plantilla,
            parametros={nombre: list(valores) for nombre, valores in entrada.parametros.items()},
            nivel=entrada.nivel,  # type: ignore[arg-type]  (validado por el cargador)
            requiere_admin=entrada.requisitos.privilegios in ("admin", "root"),
            timeout_s=entrada.timeout_s,
        )
    return whitelist


# Vista derivada del catálogo (catalogo/herramientas_llm.yaml), única fuente de verdad. Si el
# catálogo no valida, la importación falla: nunca se ejecuta con una WHITELIST a medias.
WHITELIST: dict[str, ToolSpec] = construir_whitelist(catalogo.cargar_catalogo())

# Codificación con la que PowerShell escribe su salida al estar redirigida: la página de códigos OEM
# de la consola (cp850 en un Windows en español), no la ANSI (cp1252) que Python usaría por defecto.
# Sin esto, «ó», «á» e «í» llegan como «¢», un espacio duro y «¡» (INC-10).
CODIFICACION_SALIDA = "oem" if sys.platform == "win32" else "utf-8"


def _es_administrador() -> bool:
    """Comprueba si el proceso actual se ejecuta con privilegios de administrador en Windows."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


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


def _construir_resultado(
    *,
    ok: bool,
    tool_id: str,
    comando: str | None,
    timestamp: str,
    duracion_s: float,
    data: Any = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Construye el dict de resultado con la forma común a éxitos y rechazos."""
    resultado: dict[str, Any] = {
        "ok": ok,
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

    Si estricto=False (lectura y rechazos que nunca tocaron PowerShell), un
    fallo al escribir el log solo se avisa por stderr. Si estricto=True
    (herramientas accion/mutante a punto de ejecutarse), el fallo se propaga
    para que execute() aborte antes de invocar subprocess: ninguna acción o
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
    """Ejecuta de forma segura una herramienta de la WHITELIST y audita la llamada."""
    inicio = time.monotonic()
    marca_tiempo = datetime.now(timezone.utc).isoformat()

    def _rechazar(mensaje: str, motivo: str, comando: str | None = None) -> dict[str, Any]:
        resultado = _construir_resultado(
            ok=False,
            tool_id=tool_id,
            comando=comando,
            timestamp=marca_tiempo,
            duracion_s=time.monotonic() - inicio,
            error=mensaje,
        )
        _auditar(
            tool_id=tool_id,
            params=params,
            resultado=resultado,
            motivo_rechazo=motivo,
            estricto=False,
            proveedor=proveedor,
        )
        return resultado

    # 1) tool_id desconocido
    spec = WHITELIST.get(tool_id)
    if spec is None:
        return _rechazar(f"Herramienta desconocida: '{tool_id}'.", "tool_id_desconocido")

    # 2) validación de parámetros: ni de más, ni de menos, ni fuera del enum cerrado
    claves_recibidas = set(params.keys())
    claves_declaradas = set(spec.parametros.keys())

    no_declaradas = claves_recibidas - claves_declaradas
    if no_declaradas:
        return _rechazar(
            f"Parámetro(s) no declarado(s) para '{tool_id}': {sorted(no_declaradas)}.",
            "parametro_no_declarado",
        )

    faltantes = claves_declaradas - claves_recibidas
    if faltantes:
        return _rechazar(
            f"Falta(n) parámetro(s) obligatorio(s) para '{tool_id}': {sorted(faltantes)}.",
            "parametro_faltante",
        )

    for nombre, valor in params.items():
        permitidos = spec.parametros[nombre]
        if valor not in permitidos:
            return _rechazar(
                f"Valor '{valor}' no permitido para '{nombre}' (permitidos: {permitidos}).",
                "valor_fuera_de_enum",
            )

    # 3) construir el comando SOLO a partir de la plantilla fija + valores validados
    comando_str = spec.plantilla.format(**params) if spec.parametros else spec.plantilla

    # 4) comprobación de administrador (sin intento de elevación)
    if spec.requiere_admin and not _es_administrador():
        return _rechazar(
            f"'{tool_id}' requiere privilegios de administrador. "
            "Ejecuta el proceso en una terminal elevada; ProtexiumAI no eleva permisos automáticamente.",
            "requiere_admin",
            comando=comando_str,
        )

    # 5) auditoría estricta previa para accion/mutante: si no se puede registrar,
    #    se aborta antes de tocar PowerShell.
    if spec.nivel != "lectura":
        intento = _construir_resultado(
            ok=False,
            tool_id=tool_id,
            comando=comando_str,
            timestamp=marca_tiempo,
            duracion_s=time.monotonic() - inicio,
            error="en curso",
        )
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
            return _construir_resultado(
                ok=False,
                tool_id=tool_id,
                comando=comando_str,
                timestamp=marca_tiempo,
                duracion_s=time.monotonic() - inicio,
                error=(
                    f"No se ha podido registrar la auditoría antes de ejecutar "
                    f"'{tool_id}'; ejecución abortada por seguridad ({error})."
                ),
            )

    # 6) ejecución
    comando_completo = ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", comando_str]
    try:
        proceso = subprocess.run(
            comando_completo,
            capture_output=True,
            encoding=CODIFICACION_SALIDA,
            errors="replace",
            timeout=spec.timeout_s,
        )
    except FileNotFoundError:
        resultado = _construir_resultado(
            ok=False,
            tool_id=tool_id,
            comando=comando_str,
            timestamp=marca_tiempo,
            duracion_s=time.monotonic() - inicio,
            error="No se ha encontrado powershell.exe. Este equipo requiere Windows con PowerShell en el PATH.",
        )
        _auditar(tool_id=tool_id, params=params, resultado=resultado, motivo_rechazo=None, estricto=False, proveedor=proveedor)
        return resultado
    except subprocess.TimeoutExpired:
        resultado = _construir_resultado(
            ok=False,
            tool_id=tool_id,
            comando=comando_str,
            timestamp=marca_tiempo,
            duracion_s=time.monotonic() - inicio,
            error=f"El comando ha tardado más de {spec.timeout_s} segundos y se ha cancelado.",
        )
        _auditar(tool_id=tool_id, params=params, resultado=resultado, motivo_rechazo=None, estricto=False, proveedor=proveedor)
        return resultado

    if proceso.returncode != 0:
        error_ps = proceso.stderr.strip() or "sin detalles adicionales"
        resultado = _construir_resultado(
            ok=False,
            tool_id=tool_id,
            comando=comando_str,
            timestamp=marca_tiempo,
            duracion_s=time.monotonic() - inicio,
            error=f"PowerShell devolvió un error al ejecutar '{tool_id}' ({error_ps}).",
        )
        _auditar(tool_id=tool_id, params=params, resultado=resultado, motivo_rechazo=None, estricto=False, proveedor=proveedor)
        return resultado

    salida = proceso.stdout.strip()
    try:
        datos = json.loads(salida) if salida else None
    except json.JSONDecodeError:
        resultado = _construir_resultado(
            ok=False,
            tool_id=tool_id,
            comando=comando_str,
            timestamp=marca_tiempo,
            duracion_s=time.monotonic() - inicio,
            error=f"La salida de PowerShell para '{tool_id}' no es un JSON válido: {salida!r}",
        )
        _auditar(tool_id=tool_id, params=params, resultado=resultado, motivo_rechazo=None, estricto=False, proveedor=proveedor)
        return resultado

    datos = _normalizar_datos_lista(tool_id, datos)
    resultado = _construir_resultado(
        ok=True,
        tool_id=tool_id,
        comando=comando_str,
        timestamp=marca_tiempo,
        duracion_s=time.monotonic() - inicio,
        data=datos,
    )
    _auditar(tool_id=tool_id, params=params, resultado=resultado, motivo_rechazo=None, estricto=False, proveedor=proveedor)
    return resultado
