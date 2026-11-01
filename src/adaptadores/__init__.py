"""Adaptadores por motor: los únicos módulos que ejecutan herramientas (regla 1).

Cada motor del catálogo tiene su adaptador (`powershell`, `registro`, `comando`) con la misma
interfaz (`construir` y `ejecutar`, ver `base.Adaptador`). `motor: python` está reservado y no
tiene adaptador en H1.
"""

from __future__ import annotations

from types import ModuleType

from src.adaptadores import comando, powershell, registro

ADAPTADORES: dict[str, ModuleType] = {
    powershell.MOTOR: powershell,
    registro.MOTOR: registro,
    comando.MOTOR: comando,
}


def adaptador_para(motor: str) -> ModuleType:
    """Devuelve el adaptador del motor; KeyError si no existe (la política lo impide antes)."""
    return ADAPTADORES[motor]
