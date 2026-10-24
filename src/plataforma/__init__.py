"""Detección de la plataforma en la que corre ProtexiumAI (sistema, versión, privilegios y binarios)."""

from src.plataforma.deteccion import (
    Capacidades,
    capacidades_del_equipo,
    detectar_capacidades,
    parsear_os_release,
)

__all__ = ["Capacidades", "capacidades_del_equipo", "detectar_capacidades", "parsear_os_release"]
