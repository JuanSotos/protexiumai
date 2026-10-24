"""Definición de las tools para function calling del LLM, generada a partir del catálogo YAML (vía la WHITELIST de src/executor.py) y filtrada por las capacidades del equipo."""

from __future__ import annotations

from typing import Any

from src import catalogo, executor
from src.plataforma import deteccion


def generar_tools_schema(
    capacidades: deteccion.Capacidades | None = None,
    perfil: str = catalogo.PERFIL_POR_DEFECTO,
    cat: catalogo.Catalogo | None = None,
) -> list[dict[str, Any]]:
    """Genera el array 'tools' (formato function calling del SDK openai) con las herramientas aplicables.

    La fuente de verdad es el catálogo (catalogo/herramientas_llm.yaml). La WHITELIST del
    executor es su vista derivada y se lee dinámicamente en cada llamada: el esquema nunca se
    copia a mano. Solo las entradas de tipo `herramienta` llegan al LLM; las futuras
    comprobaciones se agruparán por área en lugar de exponerse una a una.

    Solo se incluyen las herramientas que `catalogo.aplicable` da por válidas para las
    `capacidades` del equipo (por defecto, las detectadas) y el `perfil`. En un equipo sin
    herramientas aplicables (p. ej. Linux, hoy) la lista resultante está vacía. Un id de la
    WHITELIST sin entrada en el catálogo no se filtra: solo ocurre al sustituir la WHITELIST en
    los tests, y filtrar únicamente puede reducir lo que ve el LLM, nunca ampliarlo.
    """
    capacidades = capacidades if capacidades is not None else deteccion.capacidades_del_equipo()
    cat = cat if cat is not None else catalogo.cargar_catalogo()

    tools: list[dict[str, Any]] = []
    for tool_id, spec in executor.WHITELIST.items():
        entrada = cat.entradas.get(tool_id)
        if entrada is not None and not catalogo.aplicable(entrada, capacidades, perfil)[0]:
            continue
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
