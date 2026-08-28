"""Definición de las tools para function calling del LLM, generada a partir de la WHITELIST de src/executor.py."""

from __future__ import annotations

from typing import Any

from src import executor


def generar_tools_schema() -> list[dict[str, Any]]:
    """Genera el array 'tools' (formato function calling del SDK openai) a partir de executor.WHITELIST.

    La WHITELIST es la única fuente de verdad: se lee dinámicamente en cada
    llamada, nunca se copia a mano.
    """
    tools: list[dict[str, Any]] = []
    for tool_id, spec in executor.WHITELIST.items():
        propiedades = {
            nombre: {"type": "string", "enum": valores}
            for nombre, valores in spec.parametros.items()
        }
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool_id,
                    "description": spec.descripcion,
                    "parameters": {
                        "type": "object",
                        "properties": propiedades,
                        "required": list(spec.parametros.keys()),
                    },
                },
            }
        )
    return tools
