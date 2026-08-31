"""Tests de src/executor.py: WHITELIST, validación de parámetros y auditoría.

subprocess.run está siempre mockeado: ningún test de este módulo ejecuta
PowerShell real ni toca logs/audit.jsonl (ver fixture autouse en conftest.py).
"""

from __future__ import annotations

import json
import subprocess
from unittest.mock import Mock, patch

import pytest

from src import audit, executor


def _proceso_ok(stdout: str = "{}") -> Mock:
    return Mock(returncode=0, stdout=stdout, stderr="")


def test_whitelist_contiene_exactamente_las_25_herramientas():
    assert set(executor.WHITELIST) == {
        "get_defender_status",
        "get_detected_threats",
        "get_firewall_status",
        "get_active_network_profile",
        "start_quick_scan",
        "update_signatures",
        "set_firewall_profile",
        "set_block_all_incoming",
        "remove_all_threats",
        "get_account_info",
        "start_full_scan",
        "start_custom_scan",
        "get_allowed_threats",
        "get_defender_exclusions",
        "get_defender_preferences",
        "get_allowed_firewall_rules",
        "restore_firewall_defaults",
        "get_exploit_protection_status",
        "get_core_isolation_status",
        "get_secure_boot_status",
        "get_tpm_status",
        "get_bitlocker_status",
        "get_storage_status",
        "get_battery_status",
        "get_time_service_status",
    }


def test_execute_rechaza_tool_id_desconocido():
    with patch("src.executor.subprocess.run") as mock_run:
        resultado = executor.execute("borrar_disco", {})

    assert resultado["ok"] is False
    assert "desconocid" in resultado["error"].lower()
    mock_run.assert_not_called()


def test_execute_rechaza_parametro_no_declarado():
    with patch("src.executor.subprocess.run") as mock_run:
        resultado = executor.execute("start_quick_scan", {"foo": "bar"})

    assert resultado["ok"] is False
    mock_run.assert_not_called()


def test_execute_rechaza_parametro_faltante():
    with patch("src.executor.subprocess.run") as mock_run:
        resultado = executor.execute("set_firewall_profile", {"profile": "Private"})

    assert resultado["ok"] is False
    mock_run.assert_not_called()


def test_execute_rechaza_valor_fuera_de_enum():
    with patch("src.executor.subprocess.run") as mock_run:
        resultado = executor.execute(
            "set_firewall_profile", {"profile": "Evil", "enabled": "True"}
        )

    assert resultado["ok"] is False
    mock_run.assert_not_called()


def test_set_block_all_incoming_rechaza_parametro_faltante():
    with patch("src.executor.subprocess.run") as mock_run:
        resultado = executor.execute("set_block_all_incoming", {"profile": "Private"})

    assert resultado["ok"] is False
    mock_run.assert_not_called()


def test_set_block_all_incoming_rechaza_valor_fuera_de_enum():
    with patch("src.executor.subprocess.run") as mock_run:
        resultado = executor.execute(
            "set_block_all_incoming", {"profile": "Evil", "allow_inbound_rules": "False"}
        )

    assert resultado["ok"] is False
    mock_run.assert_not_called()


def test_comando_set_firewall_profile_es_exacto():
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()) as mock_run, \
         patch("src.executor._es_administrador", return_value=True):
        resultado = executor.execute(
            "set_firewall_profile", {"profile": "Private", "enabled": "True"}
        )

    assert resultado["ok"] is True
    mock_run.assert_called_once()
    comando_llamado = mock_run.call_args[0][0]
    assert comando_llamado == [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        "Set-NetFirewallProfile -Profile Private -Enabled True",
    ]


def test_comando_set_block_all_incoming_es_exacto():
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()) as mock_run, \
         patch("src.executor._es_administrador", return_value=True):
        resultado = executor.execute(
            "set_block_all_incoming", {"profile": "Private", "allow_inbound_rules": "False"}
        )

    assert resultado["ok"] is True
    mock_run.assert_called_once()
    comando_llamado = mock_run.call_args[0][0]
    assert comando_llamado == [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        "Set-NetFirewallProfile -Profile Private -AllowInboundRules False",
    ]


@pytest.mark.parametrize(
    "tool_id, params",
    [
        ("start_quick_scan", {}),
        ("update_signatures", {}),
        ("set_firewall_profile", {"profile": "Private", "enabled": "True"}),
        ("set_block_all_incoming", {"profile": "Private", "allow_inbound_rules": "False"}),
        ("remove_all_threats", {}),
        ("start_full_scan", {}),
        ("start_custom_scan", {"ruta": "Descargas"}),
        ("get_defender_exclusions", {}),
        ("restore_firewall_defaults", {}),
        ("get_secure_boot_status", {}),
        ("get_tpm_status", {}),
        ("get_bitlocker_status", {}),
    ],
)
def test_execute_bloquea_sin_admin_para_herramientas_que_lo_requieren(tool_id, params):
    with patch("src.executor.subprocess.run") as mock_run, \
         patch("src.executor._es_administrador", return_value=False):
        resultado = executor.execute(tool_id, params)

    assert resultado["ok"] is False
    assert "admin" in resultado["error"].lower()
    mock_run.assert_not_called()


def test_execute_permite_cuando_admin_y_requerido():
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()) as mock_run, \
         patch("src.executor._es_administrador", return_value=True):
        resultado = executor.execute("remove_all_threats", {})

    assert resultado["ok"] is True
    mock_run.assert_called_once()


def test_lectura_no_comprueba_admin():
    with patch("src.executor.subprocess.run", return_value=_proceso_ok('{"AMServiceEnabled": true}')), \
         patch("src.executor._es_administrador", return_value=False):
        resultado = executor.execute("get_defender_status", {})

    assert resultado["ok"] is True
    assert resultado["data"] == {"AMServiceEnabled": True}


@pytest.mark.parametrize("stdout_vacio", ["", "null"])
def test_get_detected_threats_normaliza_vacio_a_lista_vacia(stdout_vacio):
    with patch("src.executor.subprocess.run", return_value=_proceso_ok(stdout_vacio)):
        resultado = executor.execute("get_detected_threats", {})

    assert resultado["ok"] is True
    assert resultado["data"] == []


def test_get_detected_threats_normaliza_objeto_unico_a_lista():
    objeto = {"ThreatName": "EICAR"}
    with patch("src.executor.subprocess.run", return_value=_proceso_ok(json.dumps(objeto))):
        resultado = executor.execute("get_detected_threats", {})

    assert resultado["ok"] is True
    assert resultado["data"] == [objeto]


def test_get_firewall_status_no_normaliza_objeto():
    objeto = {"Name": "Domain", "Enabled": True}
    with patch("src.executor.subprocess.run", return_value=_proceso_ok(json.dumps(objeto))):
        resultado = executor.execute("get_firewall_status", {})

    assert resultado["ok"] is True
    assert resultado["data"] == objeto


def test_comando_get_firewall_status_es_exacto():
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()) as mock_run:
        resultado = executor.execute("get_firewall_status", {})

    assert resultado["ok"] is True
    mock_run.assert_called_once()
    comando_llamado = mock_run.call_args[0][0]
    assert comando_llamado == [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        (
            "Get-NetFirewallProfile | Select-Object Name, Enabled, AllowInboundRules, "
            "NotifyOnListen | ConvertTo-Json"
        ),
    ]


def test_comando_get_active_network_profile_es_exacto():
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()) as mock_run:
        resultado = executor.execute("get_active_network_profile", {})

    assert resultado["ok"] is True
    mock_run.assert_called_once()
    comando_llamado = mock_run.call_args[0][0]
    assert comando_llamado == [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        (
            "Get-NetConnectionProfile | Select-Object Name, InterfaceAlias, NetworkCategory "
            "| ConvertTo-Json"
        ),
    ]


def test_get_active_network_profile_no_comprueba_admin():
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()) as mock_run, \
         patch("src.executor._es_administrador", return_value=False):
        resultado = executor.execute("get_active_network_profile", {})

    assert resultado["ok"] is True
    mock_run.assert_called_once()


@pytest.mark.parametrize("stdout_vacio", ["", "null"])
def test_get_active_network_profile_normaliza_vacio_a_lista_vacia(stdout_vacio):
    with patch("src.executor.subprocess.run", return_value=_proceso_ok(stdout_vacio)):
        resultado = executor.execute("get_active_network_profile", {})

    assert resultado["ok"] is True
    assert resultado["data"] == []


def test_get_active_network_profile_normaliza_objeto_unico_a_lista():
    objeto = {"Name": "Red de casa", "InterfaceAlias": "Wi-Fi", "NetworkCategory": "Private"}
    with patch("src.executor.subprocess.run", return_value=_proceso_ok(json.dumps(objeto))):
        resultado = executor.execute("get_active_network_profile", {})

    assert resultado["ok"] is True
    assert resultado["data"] == [objeto]


def test_get_active_network_profile_no_normaliza_lista_ya_poblada():
    lista = [
        {"Name": "Red de casa", "InterfaceAlias": "Wi-Fi", "NetworkCategory": "Private"},
        {"Name": "VPN corporativa", "InterfaceAlias": "Ethernet 2", "NetworkCategory": "Domain"},
    ]
    with patch("src.executor.subprocess.run", return_value=_proceso_ok(json.dumps(lista))):
        resultado = executor.execute("get_active_network_profile", {})

    assert resultado["ok"] is True
    assert resultado["data"] == lista


def test_comando_get_account_info_es_exacto():
    with patch(
        "src.executor.subprocess.run",
        return_value=_proceso_ok('{"Usuario": "PC\\\\vboxuser", "EsAdministradorLocal": false}'),
    ) as mock_run:
        resultado = executor.execute("get_account_info", {})

    assert resultado["ok"] is True
    assert resultado["data"] == {"Usuario": "PC\\vboxuser", "EsAdministradorLocal": False}
    mock_run.assert_called_once()
    comando_llamado = mock_run.call_args[0][0]
    assert comando_llamado == [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        (
            "$p = New-Object Security.Principal.WindowsPrincipal("
            "[Security.Principal.WindowsIdentity]::GetCurrent()); "
            "[PSCustomObject]@{ Usuario = $p.Identity.Name; "
            "EsAdministradorLocal = $p.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator) } "
            "| ConvertTo-Json"
        ),
    ]


def test_get_account_info_no_comprueba_admin():
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()) as mock_run, \
         patch("src.executor._es_administrador", return_value=False):
        resultado = executor.execute("get_account_info", {})

    assert resultado["ok"] is True
    mock_run.assert_called_once()


def test_comando_start_full_scan_es_exacto():
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()) as mock_run, \
         patch("src.executor._es_administrador", return_value=True):
        resultado = executor.execute("start_full_scan", {})

    assert resultado["ok"] is True
    mock_run.assert_called_once()
    comando_llamado = mock_run.call_args[0][0]
    assert comando_llamado == [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        "Start-MpScan -ScanType FullScan",
    ]


@pytest.mark.parametrize("clave", ["Descargas", "Escritorio", "Documentos"])
def test_comando_start_custom_scan_es_exacto(clave):
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()) as mock_run, \
         patch("src.executor._es_administrador", return_value=True):
        resultado = executor.execute("start_custom_scan", {"ruta": clave})

    assert resultado["ok"] is True
    mock_run.assert_called_once()
    comando_llamado = mock_run.call_args[0][0]
    assert comando_llamado == [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        (
            "$rutas = @{ 'Descargas' = \"$env:USERPROFILE\\Downloads\"; "
            "'Escritorio' = \"$env:USERPROFILE\\Desktop\"; "
            "'Documentos' = \"$env:USERPROFILE\\Documents\" }; "
            f"Start-MpScan -ScanType CustomScan -ScanPath $rutas['{clave}']"
        ),
    ]


def test_start_custom_scan_rechaza_ruta_fuera_de_enum():
    with patch("src.executor.subprocess.run") as mock_run, \
         patch("src.executor._es_administrador", return_value=True):
        resultado = executor.execute("start_custom_scan", {"ruta": "C:\\Windows\\System32"})

    assert resultado["ok"] is False
    mock_run.assert_not_called()


def test_comando_get_allowed_threats_es_exacto():
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()) as mock_run:
        resultado = executor.execute("get_allowed_threats", {})

    assert resultado["ok"] is True
    mock_run.assert_called_once()
    comando_llamado = mock_run.call_args[0][0]
    assert comando_llamado == [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        (
            "Get-MpPreference | Select-Object ThreatIDDefaultAction_Ids, "
            "ThreatIDDefaultAction_Actions | ConvertTo-Json"
        ),
    ]


def test_comando_get_defender_preferences_es_exacto():
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()) as mock_run:
        resultado = executor.execute("get_defender_preferences", {})

    assert resultado["ok"] is True
    mock_run.assert_called_once()
    comando_llamado = mock_run.call_args[0][0]
    assert comando_llamado == [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        (
            "Get-MpPreference | Select-Object EnableControlledFolderAccess, "
            "MAPSReporting, SubmitSamplesConsent, PUAProtection | ConvertTo-Json"
        ),
    ]


def test_comando_get_exploit_protection_status_es_exacto():
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()) as mock_run:
        resultado = executor.execute("get_exploit_protection_status", {})

    assert resultado["ok"] is True
    mock_run.assert_called_once()
    comando_llamado = mock_run.call_args[0][0]
    assert comando_llamado == [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        "Get-ProcessMitigation -System | ConvertTo-Json -Depth 4",
    ]


def test_get_exploit_protection_status_no_comprueba_admin():
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()) as mock_run, \
         patch("src.executor._es_administrador", return_value=False):
        resultado = executor.execute("get_exploit_protection_status", {})

    assert resultado["ok"] is True
    mock_run.assert_called_once()


def test_comando_get_defender_exclusions_es_exacto():
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()) as mock_run, \
         patch("src.executor._es_administrador", return_value=True):
        resultado = executor.execute("get_defender_exclusions", {})

    assert resultado["ok"] is True
    mock_run.assert_called_once()
    comando_llamado = mock_run.call_args[0][0]
    assert comando_llamado == [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        (
            "Get-MpPreference | Select-Object ExclusionPath, ExclusionExtension, "
            "ExclusionProcess | ConvertTo-Json"
        ),
    ]


def test_get_defender_exclusions_admin_devuelve_datos_reales():
    objeto = {
        "ExclusionPath": ["C:\\Datos"],
        "ExclusionExtension": [".log"],
        "ExclusionProcess": ["backup.exe"],
    }
    with patch(
        "src.executor.subprocess.run", return_value=_proceso_ok(json.dumps(objeto))
    ), patch("src.executor._es_administrador", return_value=True):
        resultado = executor.execute("get_defender_exclusions", {})

    assert resultado["ok"] is True
    assert resultado["data"] == objeto


def test_comando_get_allowed_firewall_rules_es_exacto():
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()) as mock_run:
        resultado = executor.execute("get_allowed_firewall_rules", {})

    assert resultado["ok"] is True
    mock_run.assert_called_once()
    comando_llamado = mock_run.call_args[0][0]
    assert comando_llamado == [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        (
            "Get-NetFirewallRule -Direction Inbound -Action Allow -Enabled True | "
            "Select-Object DisplayName, Profile | ConvertTo-Json"
        ),
    ]


@pytest.mark.parametrize("stdout_vacio", ["", "null"])
def test_get_allowed_firewall_rules_normaliza_vacio_a_lista_vacia(stdout_vacio):
    with patch("src.executor.subprocess.run", return_value=_proceso_ok(stdout_vacio)):
        resultado = executor.execute("get_allowed_firewall_rules", {})

    assert resultado["ok"] is True
    assert resultado["data"] == []


def test_get_allowed_firewall_rules_normaliza_objeto_unico_a_lista():
    objeto = {"DisplayName": "Core Networking - DNS", "Profile": "Domain, Private, Public"}
    with patch("src.executor.subprocess.run", return_value=_proceso_ok(json.dumps(objeto))):
        resultado = executor.execute("get_allowed_firewall_rules", {})

    assert resultado["ok"] is True
    assert resultado["data"] == [objeto]


def test_get_allowed_firewall_rules_no_normaliza_lista_ya_poblada():
    lista = [
        {"DisplayName": "Core Networking - DNS", "Profile": "Domain, Private, Public"},
        {"DisplayName": "mDNS", "Profile": "Private"},
    ]
    with patch("src.executor.subprocess.run", return_value=_proceso_ok(json.dumps(lista))):
        resultado = executor.execute("get_allowed_firewall_rules", {})

    assert resultado["ok"] is True
    assert resultado["data"] == lista


def test_comando_restore_firewall_defaults_es_exacto():
    with patch("src.executor.subprocess.run", return_value=_proceso_ok("")) as mock_run, \
         patch("src.executor._es_administrador", return_value=True):
        resultado = executor.execute("restore_firewall_defaults", {})

    assert resultado["ok"] is True
    mock_run.assert_called_once()
    comando_llamado = mock_run.call_args[0][0]
    assert comando_llamado == [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        "netsh advfirewall reset | Out-Null",
    ]


def test_comando_get_core_isolation_status_es_exacto():
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()) as mock_run:
        resultado = executor.execute("get_core_isolation_status", {})

    assert resultado["ok"] is True
    mock_run.assert_called_once()
    comando_llamado = mock_run.call_args[0][0]
    assert comando_llamado == [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        (
            "Get-CimInstance -Namespace root\\Microsoft\\Windows\\DeviceGuard "
            "-ClassName Win32_DeviceGuard | ConvertTo-Json -Depth 3"
        ),
    ]


def test_get_core_isolation_status_no_comprueba_admin():
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()) as mock_run, \
         patch("src.executor._es_administrador", return_value=False):
        resultado = executor.execute("get_core_isolation_status", {})

    assert resultado["ok"] is True
    mock_run.assert_called_once()


def test_comando_get_secure_boot_status_es_exacto():
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()) as mock_run, \
         patch("src.executor._es_administrador", return_value=True):
        resultado = executor.execute("get_secure_boot_status", {})

    assert resultado["ok"] is True
    mock_run.assert_called_once()
    comando_llamado = mock_run.call_args[0][0]
    assert comando_llamado == [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        (
            "try { [PSCustomObject]@{ SecureBootEnabled = (Confirm-SecureBootUEFI) } | ConvertTo-Json } "
            "catch { [PSCustomObject]@{ SecureBootEnabled = $null; Error = $_.Exception.Message } | ConvertTo-Json }"
        ),
    ]


def test_get_secure_boot_status_admin_devuelve_datos_reales():
    objeto = {"SecureBootEnabled": True}
    with patch(
        "src.executor.subprocess.run", return_value=_proceso_ok(json.dumps(objeto))
    ), patch("src.executor._es_administrador", return_value=True):
        resultado = executor.execute("get_secure_boot_status", {})

    assert resultado["ok"] is True
    assert resultado["data"] == objeto


def test_comando_get_tpm_status_es_exacto():
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()) as mock_run, \
         patch("src.executor._es_administrador", return_value=True):
        resultado = executor.execute("get_tpm_status", {})

    assert resultado["ok"] is True
    mock_run.assert_called_once()
    comando_llamado = mock_run.call_args[0][0]
    assert comando_llamado == [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        (
            "Get-Tpm | Select-Object TpmPresent, TpmReady, TpmEnabled, TpmActivated, "
            "ManufacturerIdTxt, ManufacturerVersion | ConvertTo-Json"
        ),
    ]


def test_get_tpm_status_admin_devuelve_datos_reales():
    objeto = {
        "TpmPresent": True,
        "TpmReady": True,
        "TpmEnabled": True,
        "TpmActivated": True,
        "ManufacturerIdTxt": "IFX",
        "ManufacturerVersion": "7.2",
    }
    with patch(
        "src.executor.subprocess.run", return_value=_proceso_ok(json.dumps(objeto))
    ), patch("src.executor._es_administrador", return_value=True):
        resultado = executor.execute("get_tpm_status", {})

    assert resultado["ok"] is True
    assert resultado["data"] == objeto


def test_comando_get_bitlocker_status_es_exacto():
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()) as mock_run, \
         patch("src.executor._es_administrador", return_value=True):
        resultado = executor.execute("get_bitlocker_status", {})

    assert resultado["ok"] is True
    mock_run.assert_called_once()
    comando_llamado = mock_run.call_args[0][0]
    assert comando_llamado == [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        (
            "Get-BitLockerVolume | Select-Object MountPoint, VolumeStatus, ProtectionStatus, "
            "EncryptionPercentage | ConvertTo-Json"
        ),
    ]


@pytest.mark.parametrize("stdout_vacio", ["", "null"])
def test_get_bitlocker_status_normaliza_vacio_a_lista_vacia(stdout_vacio):
    with patch(
        "src.executor.subprocess.run", return_value=_proceso_ok(stdout_vacio)
    ), patch("src.executor._es_administrador", return_value=True):
        resultado = executor.execute("get_bitlocker_status", {})

    assert resultado["ok"] is True
    assert resultado["data"] == []


def test_get_bitlocker_status_normaliza_objeto_unico_a_lista():
    objeto = {
        "MountPoint": "C:",
        "VolumeStatus": "FullyEncrypted",
        "ProtectionStatus": "On",
        "EncryptionPercentage": 100,
    }
    with patch(
        "src.executor.subprocess.run", return_value=_proceso_ok(json.dumps(objeto))
    ), patch("src.executor._es_administrador", return_value=True):
        resultado = executor.execute("get_bitlocker_status", {})

    assert resultado["ok"] is True
    assert resultado["data"] == [objeto]


def test_get_bitlocker_status_no_normaliza_lista_ya_poblada():
    lista = [
        {
            "MountPoint": "C:",
            "VolumeStatus": "FullyEncrypted",
            "ProtectionStatus": "On",
            "EncryptionPercentage": 100,
        },
        {
            "MountPoint": "D:",
            "VolumeStatus": "FullyDecrypted",
            "ProtectionStatus": "Off",
            "EncryptionPercentage": 0,
        },
    ]
    with patch(
        "src.executor.subprocess.run", return_value=_proceso_ok(json.dumps(lista))
    ), patch("src.executor._es_administrador", return_value=True):
        resultado = executor.execute("get_bitlocker_status", {})

    assert resultado["ok"] is True
    assert resultado["data"] == lista


def test_comando_get_storage_status_es_exacto():
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()) as mock_run:
        resultado = executor.execute("get_storage_status", {})

    assert resultado["ok"] is True
    mock_run.assert_called_once()
    comando_llamado = mock_run.call_args[0][0]
    assert comando_llamado == [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        (
            "Get-Volume | Where-Object { $_.DriveLetter } | Select-Object DriveLetter, "
            "FileSystemLabel, SizeRemaining, Size | ConvertTo-Json"
        ),
    ]


def test_get_storage_status_no_comprueba_admin():
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()) as mock_run, \
         patch("src.executor._es_administrador", return_value=False):
        resultado = executor.execute("get_storage_status", {})

    assert resultado["ok"] is True
    mock_run.assert_called_once()


@pytest.mark.parametrize("stdout_vacio", ["", "null"])
def test_get_storage_status_normaliza_vacio_a_lista_vacia(stdout_vacio):
    with patch("src.executor.subprocess.run", return_value=_proceso_ok(stdout_vacio)):
        resultado = executor.execute("get_storage_status", {})

    assert resultado["ok"] is True
    assert resultado["data"] == []


def test_get_storage_status_normaliza_objeto_unico_a_lista():
    objeto = {"DriveLetter": "C", "FileSystemLabel": "", "SizeRemaining": 64594350080, "Size": 498969079808}
    with patch("src.executor.subprocess.run", return_value=_proceso_ok(json.dumps(objeto))):
        resultado = executor.execute("get_storage_status", {})

    assert resultado["ok"] is True
    assert resultado["data"] == [objeto]


def test_get_storage_status_no_normaliza_lista_ya_poblada():
    lista = [
        {"DriveLetter": "D", "FileSystemLabel": "Nuevo vol", "SizeRemaining": 716779298816, "Size": 2000381014016},
        {"DriveLetter": "C", "FileSystemLabel": "", "SizeRemaining": 64594350080, "Size": 498969079808},
    ]
    with patch("src.executor.subprocess.run", return_value=_proceso_ok(json.dumps(lista))):
        resultado = executor.execute("get_storage_status", {})

    assert resultado["ok"] is True
    assert resultado["data"] == lista


def test_comando_get_battery_status_es_exacto():
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()) as mock_run:
        resultado = executor.execute("get_battery_status", {})

    assert resultado["ok"] is True
    mock_run.assert_called_once()
    comando_llamado = mock_run.call_args[0][0]
    assert comando_llamado == [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        (
            "Get-CimInstance -ClassName Win32_Battery | Select-Object EstimatedChargeRemaining, "
            "BatteryStatus | ConvertTo-Json"
        ),
    ]


def test_get_battery_status_no_comprueba_admin():
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()) as mock_run, \
         patch("src.executor._es_administrador", return_value=False):
        resultado = executor.execute("get_battery_status", {})

    assert resultado["ok"] is True
    mock_run.assert_called_once()


@pytest.mark.parametrize("stdout_vacio", ["", "null"])
def test_get_battery_status_maneja_equipo_sin_bateria_como_data_none(stdout_vacio):
    with patch("src.executor.subprocess.run", return_value=_proceso_ok(stdout_vacio)):
        resultado = executor.execute("get_battery_status", {})

    assert resultado["ok"] is True
    assert resultado["data"] is None


def test_get_battery_status_no_normaliza_objeto_a_lista():
    objeto = {"EstimatedChargeRemaining": 80, "BatteryStatus": 2}
    with patch("src.executor.subprocess.run", return_value=_proceso_ok(json.dumps(objeto))):
        resultado = executor.execute("get_battery_status", {})

    assert resultado["ok"] is True
    assert resultado["data"] == objeto


def test_comando_get_time_service_status_es_exacto():
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()) as mock_run:
        resultado = executor.execute("get_time_service_status", {})

    assert resultado["ok"] is True
    mock_run.assert_called_once()
    comando_llamado = mock_run.call_args[0][0]
    assert comando_llamado == [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        "Get-Service -Name W32Time | Select-Object Status, StartType | ConvertTo-Json",
    ]


def test_get_time_service_status_no_comprueba_admin():
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()) as mock_run, \
         patch("src.executor._es_administrador", return_value=False):
        resultado = executor.execute("get_time_service_status", {})

    assert resultado["ok"] is True
    mock_run.assert_called_once()


def test_get_time_service_status_devuelve_objeto_tal_cual():
    objeto = {"Status": 4, "StartType": 2}
    with patch("src.executor.subprocess.run", return_value=_proceso_ok(json.dumps(objeto))):
        resultado = executor.execute("get_time_service_status", {})

    assert resultado["ok"] is True
    assert resultado["data"] == objeto


def test_execute_permite_start_full_scan_cuando_admin():
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()) as mock_run, \
         patch("src.executor._es_administrador", return_value=True):
        resultado = executor.execute("start_full_scan", {})

    assert resultado["ok"] is True
    mock_run.assert_called_once()


def test_execute_permite_start_custom_scan_cuando_admin():
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()) as mock_run, \
         patch("src.executor._es_administrador", return_value=True):
        resultado = executor.execute("start_custom_scan", {"ruta": "Documentos"})

    assert resultado["ok"] is True
    mock_run.assert_called_once()


def test_audit_registra_ejecucion_exitosa_start_full_scan(ruta_audit_temporal):
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()), \
         patch("src.executor._es_administrador", return_value=True):
        executor.execute("start_full_scan", {})

    # nivel="accion" audita dos veces: el intento previo estricto (paso 5) y el
    # resultado final, igual que cualquier otra herramienta accion/mutante.
    lineas = _leer_lineas_audit(ruta_audit_temporal)
    assert len(lineas) == 2
    assert lineas[0]["tool_id"] == "start_full_scan"
    assert lineas[0]["motivo_rechazo"] is None
    assert lineas[1]["tool_id"] == "start_full_scan"
    assert lineas[1]["resultado"]["ok"] is True
    assert lineas[1]["motivo_rechazo"] is None


def test_audit_registra_rechazo_start_custom_scan_sin_admin(ruta_audit_temporal):
    with patch("src.executor.subprocess.run") as mock_run, \
         patch("src.executor._es_administrador", return_value=False):
        executor.execute("start_custom_scan", {"ruta": "Descargas"})

    mock_run.assert_not_called()
    lineas = _leer_lineas_audit(ruta_audit_temporal)
    assert len(lineas) == 1
    assert lineas[0]["tool_id"] == "start_custom_scan"
    assert lineas[0]["motivo_rechazo"] == "requiere_admin"
    assert lineas[0]["resultado"]["ok"] is False


def test_audit_registra_ejecucion_exitosa_set_block_all_incoming(ruta_audit_temporal):
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()), \
         patch("src.executor._es_administrador", return_value=True):
        executor.execute(
            "set_block_all_incoming", {"profile": "Private", "allow_inbound_rules": "False"}
        )

    lineas = _leer_lineas_audit(ruta_audit_temporal)
    assert len(lineas) == 2
    assert lineas[0]["tool_id"] == "set_block_all_incoming"
    assert lineas[0]["motivo_rechazo"] is None
    assert lineas[1]["tool_id"] == "set_block_all_incoming"
    assert lineas[1]["resultado"]["ok"] is True
    assert lineas[1]["motivo_rechazo"] is None


def test_audit_registra_rechazo_set_block_all_incoming_sin_admin(ruta_audit_temporal):
    with patch("src.executor.subprocess.run") as mock_run, \
         patch("src.executor._es_administrador", return_value=False):
        executor.execute(
            "set_block_all_incoming", {"profile": "Private", "allow_inbound_rules": "False"}
        )

    mock_run.assert_not_called()
    lineas = _leer_lineas_audit(ruta_audit_temporal)
    assert len(lineas) == 1
    assert lineas[0]["tool_id"] == "set_block_all_incoming"
    assert lineas[0]["motivo_rechazo"] == "requiere_admin"
    assert lineas[0]["resultado"]["ok"] is False


def test_audit_registra_ejecucion_exitosa_restore_firewall_defaults(ruta_audit_temporal):
    with patch("src.executor.subprocess.run", return_value=_proceso_ok("")), \
         patch("src.executor._es_administrador", return_value=True):
        executor.execute("restore_firewall_defaults", {})

    lineas = _leer_lineas_audit(ruta_audit_temporal)
    assert len(lineas) == 2
    assert lineas[0]["tool_id"] == "restore_firewall_defaults"
    assert lineas[0]["motivo_rechazo"] is None
    assert lineas[1]["tool_id"] == "restore_firewall_defaults"
    assert lineas[1]["resultado"]["ok"] is True
    assert lineas[1]["motivo_rechazo"] is None


def test_audit_registra_rechazo_restore_firewall_defaults_sin_admin(ruta_audit_temporal):
    with patch("src.executor.subprocess.run") as mock_run, \
         patch("src.executor._es_administrador", return_value=False):
        executor.execute("restore_firewall_defaults", {})

    mock_run.assert_not_called()
    lineas = _leer_lineas_audit(ruta_audit_temporal)
    assert len(lineas) == 1
    assert lineas[0]["tool_id"] == "restore_firewall_defaults"
    assert lineas[0]["motivo_rechazo"] == "requiere_admin"
    assert lineas[0]["resultado"]["ok"] is False


def test_execute_maneja_timeout():
    with patch(
        "src.executor.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=["powershell.exe"], timeout=15),
    ):
        resultado = executor.execute("get_defender_status", {})

    assert resultado["ok"] is False
    assert "tardado" in resultado["error"].lower()


def test_execute_maneja_powershell_no_encontrado():
    with patch("src.executor.subprocess.run", side_effect=FileNotFoundError()):
        resultado = executor.execute("get_defender_status", {})

    assert resultado["ok"] is False
    assert "powershell.exe" in resultado["error"]


def test_execute_maneja_returncode_no_cero():
    proceso = Mock(returncode=1, stdout="", stderr="algo falló")
    with patch("src.executor.subprocess.run", return_value=proceso):
        resultado = executor.execute("get_defender_status", {})

    assert resultado["ok"] is False
    assert "algo falló" in resultado["error"]


def test_execute_maneja_json_invalido():
    with patch("src.executor.subprocess.run", return_value=_proceso_ok("no es json")):
        resultado = executor.execute("get_defender_status", {})

    assert resultado["ok"] is False
    assert "json" in resultado["error"].lower()


def _leer_lineas_audit(ruta_audit_temporal) -> list[dict]:
    if not ruta_audit_temporal.exists():
        return []
    return [
        json.loads(linea)
        for linea in ruta_audit_temporal.read_text(encoding="utf-8").splitlines()
        if linea.strip()
    ]


def test_audit_registra_ejecucion_exitosa(ruta_audit_temporal):
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()):
        executor.execute("get_defender_status", {})

    lineas = _leer_lineas_audit(ruta_audit_temporal)
    assert len(lineas) == 1
    assert lineas[0]["tool_id"] == "get_defender_status"
    assert lineas[0]["resultado"]["ok"] is True
    assert lineas[0]["motivo_rechazo"] is None


@pytest.mark.parametrize(
    "tool_id", ["get_storage_status", "get_battery_status", "get_time_service_status"]
)
def test_audit_registra_ejecucion_exitosa_grupo6(ruta_audit_temporal, tool_id):
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()):
        executor.execute(tool_id, {})

    lineas = _leer_lineas_audit(ruta_audit_temporal)
    assert len(lineas) == 1
    assert lineas[0]["tool_id"] == tool_id
    assert lineas[0]["resultado"]["ok"] is True
    assert lineas[0]["motivo_rechazo"] is None


def test_audit_registra_rechazo_con_motivo(ruta_audit_temporal):
    executor.execute("desconocido", {})

    lineas = _leer_lineas_audit(ruta_audit_temporal)
    assert len(lineas) == 1
    assert lineas[0]["motivo_rechazo"] == "tool_id_desconocido"
    assert lineas[0]["resultado"]["ok"] is False


def test_audit_acumula_varias_llamadas(ruta_audit_temporal):
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()):
        executor.execute("get_defender_status", {})
    executor.execute("desconocido", {})

    lineas = _leer_lineas_audit(ruta_audit_temporal)
    assert len(lineas) == 2
    assert lineas[0]["tool_id"] == "get_defender_status"
    assert lineas[1]["tool_id"] == "desconocido"


def test_audit_propaga_proveedor(ruta_audit_temporal):
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()):
        executor.execute("get_defender_status", {}, proveedor="ollama")

    lineas = _leer_lineas_audit(ruta_audit_temporal)
    assert len(lineas) == 1
    assert lineas[0]["proveedor"] == "ollama"


def test_audit_proveedor_por_defecto_es_none(ruta_audit_temporal):
    with patch("src.executor.subprocess.run", return_value=_proceso_ok()):
        executor.execute("get_defender_status", {})

    lineas = _leer_lineas_audit(ruta_audit_temporal)
    assert lineas[0]["proveedor"] is None


def test_execute_aborta_mutante_si_falla_auditoria_previa():
    with patch("src.executor.subprocess.run") as mock_run, \
         patch("src.executor._es_administrador", return_value=True), \
         patch.object(audit, "registrar_auditoria", side_effect=OSError("disco lleno")):
        resultado = executor.execute("remove_all_threats", {})

    assert resultado["ok"] is False
    mock_run.assert_not_called()
