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


def test_whitelist_contiene_exactamente_las_7_herramientas():
    assert set(executor.WHITELIST) == {
        "get_defender_status",
        "get_detected_threats",
        "get_firewall_status",
        "start_quick_scan",
        "update_signatures",
        "set_firewall_profile",
        "remove_all_threats",
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


@pytest.mark.parametrize(
    "tool_id, params",
    [
        ("start_quick_scan", {}),
        ("update_signatures", {}),
        ("set_firewall_profile", {"profile": "Private", "enabled": "True"}),
        ("remove_all_threats", {}),
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


def test_execute_aborta_mutante_si_falla_auditoria_previa():
    with patch("src.executor.subprocess.run") as mock_run, \
         patch("src.executor._es_administrador", return_value=True), \
         patch.object(audit, "registrar_auditoria", side_effect=OSError("disco lleno")):
        resultado = executor.execute("remove_all_threats", {})

    assert resultado["ok"] is False
    mock_run.assert_not_called()
