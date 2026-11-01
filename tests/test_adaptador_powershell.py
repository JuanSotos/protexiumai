"""Tests del adaptador `powershell` (regla 11). subprocess.run está siempre mockeado."""

from __future__ import annotations

import json
import subprocess
import sys
from unittest.mock import Mock, patch

import pytest

from src import catalogo
from src.adaptadores import powershell

CATALOGO = catalogo.cargar_catalogo()


def _proceso(stdout: str = "{}", returncode: int = 0, stderr: str = "") -> Mock:
    return Mock(returncode=returncode, stdout=stdout, stderr=stderr)


def _invocacion(tool_id: str = "get_defender_status", params: dict[str, str] | None = None):
    return powershell.construir(CATALOGO.entradas[tool_id], params or {})


def test_construir_formatea_la_plantilla_y_monta_la_linea_exacta():
    invocacion = _invocacion("set_firewall_profile", {"profile": "Private", "enabled": "True"})
    assert invocacion.texto == "Set-NetFirewallProfile -Profile Private -Enabled True"
    assert invocacion.argv == (
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
        "Set-NetFirewallProfile -Profile Private -Enabled True",
    )
    assert invocacion.timeout_s == CATALOGO.entradas["set_firewall_profile"].timeout_s


def test_sin_parametros_la_plantilla_se_usa_tal_cual():
    entrada = CATALOGO.entradas["get_storage_status"]
    assert _invocacion("get_storage_status").texto == entrada.plantilla


def test_en_windows_se_lanza_sin_ventana_y_con_la_codificacion_oem(monkeypatch):
    monkeypatch.setattr(powershell.sys, "platform", "win32")
    with patch("src.adaptadores.powershell.subprocess.run", return_value=_proceso()) as mock_run:
        powershell.ejecutar(_invocacion())

    argumentos = mock_run.call_args.kwargs
    assert mock_run.call_args.args[0][:4] == ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command"]
    assert argumentos["creationflags"] == powershell.CREATE_NO_WINDOW == 0x08000000
    assert argumentos["encoding"] == powershell.CODIFICACION_SALIDA
    assert argumentos["errors"] == "replace"
    assert argumentos["timeout"] == CATALOGO.entradas["get_defender_status"].timeout_s
    assert "shell" not in argumentos


def test_fuera_de_windows_no_se_pasa_creationflags(monkeypatch):
    monkeypatch.setattr(powershell.sys, "platform", "linux")
    with patch("src.adaptadores.powershell.subprocess.run", return_value=_proceso()) as mock_run:
        powershell.ejecutar(_invocacion())
    assert "creationflags" not in mock_run.call_args.kwargs


@pytest.mark.skipif(sys.platform != "win32", reason="La codificación OEM solo existe en Windows")
def test_en_windows_la_codificacion_es_la_oem():
    assert powershell.CODIFICACION_SALIDA == "oem"


def test_salida_json_valida_se_devuelve_como_datos():
    with patch("src.adaptadores.powershell.subprocess.run", return_value=_proceso('{"AMServiceEnabled": true}')):
        salida = powershell.ejecutar(_invocacion())
    assert salida.estado == "ok"
    assert salida.datos == {"AMServiceEnabled": True}


def test_powershell_ausente_es_no_aplicable():
    with patch("src.adaptadores.powershell.subprocess.run", side_effect=FileNotFoundError()):
        salida = powershell.ejecutar(_invocacion())
    assert salida.estado == "no_aplicable"
    assert "powershell.exe" in salida.error


def test_timeout_es_error():
    with patch(
        "src.adaptadores.powershell.subprocess.run",
        side_effect=subprocess.TimeoutExpired(cmd=["powershell.exe"], timeout=1),
    ):
        salida = powershell.ejecutar(_invocacion())
    assert salida.estado == "error"
    assert "tardado" in salida.error


@pytest.mark.parametrize("stderr, esperado", [("algo falló", "algo falló"), ("", "sin detalles adicionales")])
def test_codigo_de_salida_distinto_de_cero_es_error(stderr, esperado):
    with patch("src.adaptadores.powershell.subprocess.run", return_value=_proceso("", 1, stderr)):
        salida = powershell.ejecutar(_invocacion())
    assert salida.estado == "error"
    assert esperado in salida.error


def test_json_invalido_es_error():
    with patch("src.adaptadores.powershell.subprocess.run", return_value=_proceso("no es json")):
        salida = powershell.ejecutar(_invocacion())
    assert salida.estado == "error"
    assert "JSON" in salida.error


@pytest.mark.parametrize(
    "tool_id, stdout, esperado",
    [
        ("get_detected_threats", "", []),
        ("get_detected_threats", json.dumps({"a": 1}), [{"a": 1}]),
        ("get_detected_threats", json.dumps([{"a": 1}, {"b": 2}]), [{"a": 1}, {"b": 2}]),
        ("get_battery_status", "", None),
        ("get_firewall_status", json.dumps({"a": 1}), {"a": 1}),
    ],
)
def test_la_normalizacion_de_listas_se_conserva(tool_id, stdout, esperado):
    with patch("src.adaptadores.powershell.subprocess.run", return_value=_proceso(stdout)):
        salida = powershell.ejecutar(_invocacion(tool_id))
    assert salida.datos == esperado
