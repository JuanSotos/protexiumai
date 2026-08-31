"""Capa ejecutora: WHITELIST de cmdlets de PowerShell permitidos, validación de parámetros, niveles de acción y ejecución segura."""

from __future__ import annotations

import ctypes
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

from src import audit


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


WHITELIST: dict[str, ToolSpec] = {
    "get_defender_status": ToolSpec(
        id="get_defender_status",
        descripcion=(
            "Consulta el estado general de Windows Defender (protección en tiempo "
            "real, servicio, firmas, últimos análisis)."
        ),
        plantilla=(
            "Get-MpComputerStatus | Select-Object AMServiceEnabled, AntispywareEnabled, "
            "AntivirusEnabled, RealTimeProtectionEnabled, NISEnabled, "
            "AntivirusSignatureLastUpdated, AntispywareSignatureLastUpdated, "
            "QuickScanEndTime, FullScanEndTime, ComputerState | ConvertTo-Json"
        ),
        parametros={},
        nivel="lectura",
        requiere_admin=False,
        timeout_s=15,
    ),
    "get_detected_threats": ToolSpec(
        id="get_detected_threats",
        descripcion="Lista las amenazas detectadas por Windows Defender.",
        plantilla="Get-MpThreatDetection | ConvertTo-Json -Depth 3",
        parametros={},
        nivel="lectura",
        requiere_admin=False,
        timeout_s=15,
    ),
    "get_firewall_status": ToolSpec(
        id="get_firewall_status",
        descripcion=(
            "Consulta el estado (activado/desactivado) de los perfiles del firewall de "
            "Windows, si las conexiones entrantes están bloqueadas por completo "
            "(AllowInboundRules) y si el firewall notifica al bloquear una app "
            "(NotifyOnListen)."
        ),
        plantilla=(
            "Get-NetFirewallProfile | Select-Object Name, Enabled, AllowInboundRules, "
            "NotifyOnListen | ConvertTo-Json"
        ),
        parametros={},
        nivel="lectura",
        requiere_admin=False,
        timeout_s=15,
    ),
    "get_active_network_profile": ToolSpec(
        id="get_active_network_profile",
        descripcion=(
            "Consulta qué perfil de red (Dominio/Privada/Pública) está activo ahora mismo y "
            "en qué red, complementando el estado de los tres perfiles del firewall."
        ),
        plantilla=(
            "Get-NetConnectionProfile | Select-Object Name, InterfaceAlias, NetworkCategory "
            "| ConvertTo-Json"
        ),
        parametros={},
        nivel="lectura",
        requiere_admin=False,
        timeout_s=15,
    ),
    "start_quick_scan": ToolSpec(
        id="start_quick_scan",
        descripcion="Inicia un análisis rápido de Windows Defender.",
        plantilla="Start-MpScan -ScanType QuickScan",
        parametros={},
        nivel="accion",
        requiere_admin=True,
        timeout_s=600,
    ),
    "update_signatures": ToolSpec(
        id="update_signatures",
        descripcion="Actualiza las firmas de virus de Windows Defender.",
        plantilla="Update-MpSignature",
        parametros={},
        nivel="accion",
        requiere_admin=True,
        timeout_s=120,
    ),
    "set_firewall_profile": ToolSpec(
        id="set_firewall_profile",
        descripcion="Activa o desactiva un perfil concreto del firewall de Windows.",
        plantilla="Set-NetFirewallProfile -Profile {profile} -Enabled {enabled}",
        parametros={
            "profile": ["Domain", "Private", "Public"],
            "enabled": ["True", "False"],
        },
        nivel="mutante",
        requiere_admin=True,
        timeout_s=30,
    ),
    "set_block_all_incoming": ToolSpec(
        id="set_block_all_incoming",
        descripcion=(
            "Bloquea o permite TODAS las conexiones entrantes en un perfil del firewall de "
            "Windows. Poner allow_inbound_rules en 'False' bloquea absolutamente todas las "
            "conexiones entrantes, incluidas las de las apps de la lista de permitidas — es "
            "la opción 'Bloquea todas las conexiones entrantes, incluidas las de la lista de "
            "apps permitidas' de la configuración de Windows. Poner 'True' restaura el "
            "comportamiento normal (se respeta la lista de apps permitidas)."
        ),
        plantilla="Set-NetFirewallProfile -Profile {profile} -AllowInboundRules {allow_inbound_rules}",
        parametros={
            "profile": ["Domain", "Private", "Public"],
            "allow_inbound_rules": ["True", "False"],
        },
        nivel="mutante",
        requiere_admin=True,
        timeout_s=30,
    ),
    "remove_all_threats": ToolSpec(
        id="remove_all_threats",
        descripcion="Elimina todas las amenazas detectadas actualmente por Windows Defender.",
        plantilla="Remove-MpThreat",
        parametros={},
        nivel="mutante",
        requiere_admin=True,
        timeout_s=60,
    ),
    # Única herramienta del grupo "Account protection" de Windows Security. El resto del
    # grupo (Windows Hello, Dynamic lock, gestión de la cuenta Microsoft) no tiene cmdlets de
    # PowerShell oficiales equivalentes a Get/Set-MpPreference o Get/Set-NetFirewallProfile, y
    # roza la regla "sin credenciales" de CLAUDE.md al tratarse de factores de autenticación.
    # Detalle completo de la decisión en docs/cobertura_windows_security.md.
    "get_account_info": ToolSpec(
        id="get_account_info",
        descripcion=(
            "Consulta el nombre de la cuenta de Windows con la que se ha iniciado sesión y si "
            "pertenece al grupo de administradores locales."
        ),
        plantilla=(
            "$p = New-Object Security.Principal.WindowsPrincipal("
            "[Security.Principal.WindowsIdentity]::GetCurrent()); "
            "[PSCustomObject]@{ Usuario = $p.Identity.Name; "
            "EsAdministradorLocal = $p.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator) } "
            "| ConvertTo-Json"
        ),
        parametros={},
        nivel="lectura",
        requiere_admin=False,
        timeout_s=15,
    ),
    "start_full_scan": ToolSpec(
        id="start_full_scan",
        descripcion="Inicia un análisis completo de Windows Defender sobre todo el equipo.",
        plantilla="Start-MpScan -ScanType FullScan",
        parametros={},
        nivel="accion",
        requiere_admin=True,
        timeout_s=3600,
    ),
    "start_custom_scan": ToolSpec(
        id="start_custom_scan",
        descripcion=(
            "Inicia un análisis de Windows Defender sobre una carpeta de usuario "
            "predefinida (Descargas, Escritorio o Documentos)."
        ),
        plantilla=(
            "$rutas = @{{ 'Descargas' = \"$env:USERPROFILE\\Downloads\"; "
            "'Escritorio' = \"$env:USERPROFILE\\Desktop\"; "
            "'Documentos' = \"$env:USERPROFILE\\Documents\" }}; "
            "Start-MpScan -ScanType CustomScan -ScanPath $rutas['{ruta}']"
        ),
        parametros={"ruta": ["Descargas", "Escritorio", "Documentos"]},
        nivel="accion",
        requiere_admin=True,
        timeout_s=900,
    ),
    # Get-MpThreatCatalog se descartó tras comprobarlo en real: es el catálogo completo de
    # definiciones de amenazas de Defender (no las excepciones permitidas por el usuario) y
    # lanzó OutOfMemoryException tras más de 120s. Get-MpPreference sí expone directamente las
    # excepciones del usuario en ThreatIDDefaultAction_Ids/Actions, de forma inmediata.
    "get_allowed_threats": ToolSpec(
        id="get_allowed_threats",
        descripcion="Consulta las amenazas que el usuario ha permitido explícitamente en Windows Defender.",
        plantilla=(
            "Get-MpPreference | Select-Object ThreatIDDefaultAction_Ids, "
            "ThreatIDDefaultAction_Actions | ConvertTo-Json"
        ),
        parametros={},
        nivel="lectura",
        requiere_admin=False,
        timeout_s=15,
    ),
    # Comprobado en real: sin terminal elevada, Get-MpPreference devuelve el string "N/A: Must
    # be an administrator to view exclusions" en vez de las exclusiones reales. requiere_admin=True
    # hace que sin admin se devuelva el mensaje estándar de "requiere administrador" en vez de ese
    # placeholder tratado como si fueran datos.
    "get_defender_exclusions": ToolSpec(
        id="get_defender_exclusions",
        descripcion="Consulta las exclusiones configuradas actualmente en Windows Defender (rutas, extensiones y procesos).",
        plantilla=(
            "Get-MpPreference | Select-Object ExclusionPath, ExclusionExtension, "
            "ExclusionProcess | ConvertTo-Json"
        ),
        parametros={},
        nivel="lectura",
        requiere_admin=True,
        timeout_s=15,
    ),
    # No incluye "Dev Drive protection": comprobado con Get-Member sobre Get-MpPreference en la
    # versión de Defender instalada y el campo no existe en esta instalación.
    "get_defender_preferences": ToolSpec(
        id="get_defender_preferences",
        descripcion=(
            "Consulta ajustes de protección de Windows Defender: Controlled Folder Access, "
            "protección en la nube, envío automático de muestras y si el bloqueo de "
            "aplicaciones potencialmente no deseadas (PUA) está activo."
        ),
        plantilla=(
            "Get-MpPreference | Select-Object EnableControlledFolderAccess, "
            "MAPSReporting, SubmitSamplesConsent, PUAProtection | ConvertTo-Json"
        ),
        parametros={},
        nivel="lectura",
        requiere_admin=False,
        timeout_s=15,
    ),
    "get_exploit_protection_status": ToolSpec(
        id="get_exploit_protection_status",
        descripcion=(
            "Consulta la configuración de Exploit Protection a nivel de sistema (DEP, ASLR, "
            "CFG, SEHOP y el resto de mitigaciones que expone Get-ProcessMitigation)."
        ),
        plantilla="Get-ProcessMitigation -System | ConvertTo-Json -Depth 4",
        parametros={},
        nivel="lectura",
        requiere_admin=False,
        timeout_s=30,
    ),
    "get_allowed_firewall_rules": ToolSpec(
        id="get_allowed_firewall_rules",
        descripcion=(
            "Consulta de solo lectura de las reglas de entrada actualmente habilitadas y "
            "permitidas en el firewall de Windows (nombre visible de la regla y perfil al "
            "que aplica). No crea, habilita ni deshabilita ninguna regla."
        ),
        plantilla=(
            "Get-NetFirewallRule -Direction Inbound -Action Allow -Enabled True | "
            "Select-Object DisplayName, Profile | ConvertTo-Json"
        ),
        parametros={},
        nivel="lectura",
        requiere_admin=False,
        timeout_s=20,
    ),
    # netsh no produce salida por stdout gracias a "| Out-Null": el parseo de execute() trata
    # cualquier stdout no vacío como JSON obligatorio, y `netsh advfirewall reset` puede
    # imprimir texto de confirmación (no JSON) en algunas versiones de Windows. Silenciarlo
    # replica el comportamiento del resto de herramientas mutantes (sin salida por defecto).
    "restore_firewall_defaults": ToolSpec(
        id="restore_firewall_defaults",
        descripcion=(
            "ACCIÓN DE ALTO IMPACTO: restaura TODAS las reglas del firewall de Windows a los "
            "valores de fábrica, incluidas las reglas personalizadas que el usuario haya "
            "creado fuera de ProtexiumAI. No se puede deshacer."
        ),
        plantilla="netsh advfirewall reset | Out-Null",
        parametros={},
        nivel="mutante",
        requiere_admin=True,
        timeout_s=60,
    ),
    "get_core_isolation_status": ToolSpec(
        id="get_core_isolation_status",
        descripcion=(
            "Consulta el estado de Core isolation (integridad de memoria/HVCI, "
            "Credential Guard, System Guard) mediante la clase WMI oficial de Device Guard."
        ),
        plantilla=(
            "Get-CimInstance -Namespace root\\Microsoft\\Windows\\DeviceGuard "
            "-ClassName Win32_DeviceGuard | ConvertTo-Json -Depth 3"
        ),
        parametros={},
        nivel="lectura",
        requiere_admin=False,
        timeout_s=15,
    ),
    # Comprobado en real: Confirm-SecureBootUEFI sin admin no lanza la excepción de "BIOS
    # heredado" que motivó el try/catch, sino "Acceso denegado" — el try/catch la captura igual
    # y devuelve JSON válido, pero con SecureBootEnabled=null, ocultando el valor real. Igual que
    # en get_defender_exclusions, requiere_admin=True evita devolver ese placeholder como si
    # fueran datos reales.
    "get_secure_boot_status": ToolSpec(
        id="get_secure_boot_status",
        descripcion="Consulta si el arranque seguro (Secure Boot) está activo.",
        plantilla=(
            "try { [PSCustomObject]@{ SecureBootEnabled = (Confirm-SecureBootUEFI) } | ConvertTo-Json } "
            "catch { [PSCustomObject]@{ SecureBootEnabled = $null; Error = $_.Exception.Message } | ConvertTo-Json }"
        ),
        parametros={},
        nivel="lectura",
        requiere_admin=True,
        timeout_s=15,
    ),
    # Comprobado en real: sin admin, Get-Tpm no lanza error — devuelve los seis campos a $null,
    # un JSON válido pero sin ningún dato real. requiere_admin=True evita tratar ese relleno
    # como si fuera el estado real del TPM.
    "get_tpm_status": ToolSpec(
        id="get_tpm_status",
        descripcion=(
            "Consulta el estado del procesador de seguridad (TPM): si está presente, "
            "listo, activado y su fabricante/versión."
        ),
        plantilla=(
            "Get-Tpm | Select-Object TpmPresent, TpmReady, TpmEnabled, TpmActivated, "
            "ManufacturerIdTxt, ManufacturerVersion | ConvertTo-Json"
        ),
        parametros={},
        nivel="lectura",
        requiere_admin=True,
        timeout_s=15,
    ),
    # Comprobado en real: sin admin, Get-BitLockerVolume falla con "Acceso denegado" y no
    # produce ninguna salida por stdout (solo errores no terminales por stderr), lo que
    # _normalizar_datos_lista convertiría en una lista vacía indistinguible de "sin volúmenes
    # BitLocker". requiere_admin=True evita ese falso negativo.
    "get_bitlocker_status": ToolSpec(
        id="get_bitlocker_status",
        descripcion="Consulta el estado de cifrado de dispositivo (BitLocker) de los volúmenes del equipo.",
        plantilla=(
            "Get-BitLockerVolume | Select-Object MountPoint, VolumeStatus, ProtectionStatus, "
            "EncryptionPercentage | ConvertTo-Json"
        ),
        parametros={},
        nivel="lectura",
        requiere_admin=True,
        timeout_s=15,
    ),
    "get_storage_status": ToolSpec(
        id="get_storage_status",
        descripcion="Consulta el espacio libre y total de las unidades de almacenamiento del equipo.",
        plantilla=(
            "Get-Volume | Where-Object { $_.DriveLetter } | Select-Object DriveLetter, "
            "FileSystemLabel, SizeRemaining, Size | ConvertTo-Json"
        ),
        parametros={},
        nivel="lectura",
        requiere_admin=False,
        timeout_s=15,
    ),
    # Comprobado en real: sin batería (equipo de sobremesa), Get-CimInstance Win32_Battery no
    # produce ninguna salida por stdout (ni error, ni JSON vacío) — execute() la interpreta
    # como data=None, que el agente debe explicar como "este equipo no tiene batería", no como
    # un fallo de la herramienta.
    "get_battery_status": ToolSpec(
        id="get_battery_status",
        descripcion=(
            "Consulta el estado y la carga estimada de la batería. Si el equipo es de "
            "sobremesa y no tiene batería, la consulta no falla: no hay salida de PowerShell "
            "y el resultado es data=None, que debe explicarse al usuario como 'este equipo no "
            "tiene batería', nunca como un error o un fallo de la herramienta."
        ),
        plantilla=(
            "Get-CimInstance -ClassName Win32_Battery | Select-Object EstimatedChargeRemaining, "
            "BatteryStatus | ConvertTo-Json"
        ),
        parametros={},
        nivel="lectura",
        requiere_admin=False,
        timeout_s=15,
    ),
    "get_time_service_status": ToolSpec(
        id="get_time_service_status",
        descripcion=(
            "Consulta si el servicio de hora de Windows (sincronización del reloj del "
            "sistema) está en ejecución."
        ),
        plantilla="Get-Service -Name W32Time | Select-Object Status, StartType | ConvertTo-Json",
        parametros={},
        nivel="lectura",
        requiere_admin=False,
        timeout_s=15,
    ),
}


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
        proceso = subprocess.run(comando_completo, capture_output=True, text=True, timeout=spec.timeout_s)
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
