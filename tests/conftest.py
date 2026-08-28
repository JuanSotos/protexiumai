"""Fixtures compartidas: aíslan los tests de executor/audit del sistema real."""

import pytest

from src import audit


@pytest.fixture(autouse=True)
def ruta_audit_temporal(tmp_path, monkeypatch):
    """Redirige logs/audit.jsonl a un directorio temporal en todos los tests."""
    monkeypatch.setattr(audit, "RUTA_LOG", tmp_path / "logs" / "audit.jsonl")
    yield audit.RUTA_LOG
