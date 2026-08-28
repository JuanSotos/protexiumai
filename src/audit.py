"""Registro de auditoría: escribe en logs/audit.jsonl cada llamada al executor (aceptada o rechazada) con timestamp, herramienta, parámetros, proveedor y resultado."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

RUTA_LOG = Path("logs") / "audit.jsonl"


def registrar_auditoria(
    *,
    tool_id: str,
    params: dict[str, Any],
    resultado: dict[str, Any],
    motivo_rechazo: str | None = None,
    proveedor: str | None = None,
) -> None:
    """Añade una línea JSON al log de auditoría con el resultado de una llamada al executor.

    Se registra tanto si la llamada fue aceptada y ejecutada como si fue rechazada
    en cualquier fase de la validación. No captura errores de escritura (OSError):
    es responsabilidad de quien llama decidir si un fallo de auditoría debe
    bloquear la ejecución (herramientas de nivel accion/mutante) o solo avisarse.
    """
    entrada = {
        "timestamp": resultado.get("timestamp"),
        "tool_id": tool_id,
        "params": params,
        "resultado": resultado,
        "motivo_rechazo": motivo_rechazo,
        "proveedor": proveedor,
    }
    RUTA_LOG.parent.mkdir(parents=True, exist_ok=True)
    with RUTA_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entrada, ensure_ascii=False) + "\n")
