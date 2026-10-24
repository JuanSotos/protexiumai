"""Fixtures compartidas: aíslan los tests de executor/audit/plataforma del sistema real."""

import pytest

from src import audit
from src.plataforma import deteccion


@pytest.fixture(autouse=True)
def ruta_audit_temporal(tmp_path, monkeypatch):
    """Redirige logs/audit.jsonl a un directorio temporal en todos los tests."""
    monkeypatch.setattr(audit, "RUTA_LOG", tmp_path / "logs" / "audit.jsonl")
    yield audit.RUTA_LOG


@pytest.fixture(autouse=True)
def equipo_windows_11(monkeypatch):
    """Simula un Windows 11 Pro (build 26100) para que los tests no dependan del equipo real.

    Se sustituyen los lectores de bajo nivel (registro y comprobación de administrador), de modo
    que la detección completa corre sobre datos simulados. Los tests que necesiten otro equipo
    vuelven a parchear estos lectores o pasan sus propias `Capacidades`.
    """
    monkeypatch.setattr(deteccion, "_sistema_operativo", lambda: "windows")
    monkeypatch.setattr(
        deteccion,
        "_leer_registro_windows",
        lambda: {"CurrentBuildNumber": "26100", "UBR": 1000, "EditionID": "Professional", "DisplayVersion": "24H2"},
    )
    monkeypatch.setattr(deteccion, "_es_administrador_windows", lambda: False)
    deteccion.capacidades_del_equipo.cache_clear()
    yield
    deteccion.capacidades_del_equipo.cache_clear()
