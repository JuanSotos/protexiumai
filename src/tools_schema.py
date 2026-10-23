"""Definición de las tools para function calling del LLM, generada a partir del catálogo YAML (vía la WHITELIST de src/executor.py)."""

from __future__ import annotations

from typing import Any

from src import executor


def generar_tools_schema() -> list[dict[str, Any]]:
    """Genera el array 'tools' (formato function calling del SDK openai) a partir de executor.WHITELIST.

    La fuente de verdad es el catálogo (catalogo/herramientas_llm.yaml). La WHITELIST del
    executor es su vista derivada y se lee dinámicamente en cada llamada: el esquema nunca se
    copia a mano. Solo las entradas de tipo `herramienta` llegan al LLM; las futuras
    comprobaciones se agruparán por área en lugar de exponerse una a una.
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
