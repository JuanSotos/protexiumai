"""Diagnóstico: `python -m src.plataforma` imprime las capacidades del equipo en JSON."""

from __future__ import annotations

import json

from src.plataforma.deteccion import capacidades_del_equipo


def main() -> None:
    """Imprime las capacidades detectadas (sin usuario ni nombre del equipo)."""
    print(json.dumps(capacidades_del_equipo().a_dict(), indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
