"""Chat por consola para interactuar con el agente de ProtexiumAI."""

from __future__ import annotations

import sys
from typing import Any

from openai import APIConnectionError, APIError, AuthenticationError

from src.agent import Agent

sys.stdout.reconfigure(encoding="utf-8")


def confirmar_por_consola(tool_id: str, descripcion: str, params: dict[str, Any]) -> bool:
    """Pide confirmación explícita al usuario antes de ejecutar una herramienta accion/mutante."""
    detalle = f" con parámetros {params}" if params else ""
    respuesta = input(f"¿Ejecutar «{descripcion}»{detalle}? [s/n]: ").strip().lower()
    return respuesta == "s"


def main() -> None:
    try:
        agente = Agent(confirmar=confirmar_por_consola)
    except ValueError as error:
        print(f"Error de configuración: {error}", file=sys.stderr)
        sys.exit(1)

    print("ProtexiumAI — escribe 'salir' para terminar.\n")

    while True:
        mensaje = input("Tú: ").strip()
        if mensaje.lower() == "salir":
            break
        if not mensaje:
            continue

        try:
            resultado = agente.enviar_mensaje(mensaje)
        except AuthenticationError:
            print("Error: la API key no es válida. Revisa GROQ_API_KEY en .env.\n", file=sys.stderr)
            continue
        except APIConnectionError:
            print("Error: no se ha podido conectar con el proveedor LLM. Comprueba tu conexión.\n", file=sys.stderr)
            continue
        except APIError as error:
            print(f"Error al llamar al proveedor LLM: {error}\n", file=sys.stderr)
            continue

        for herramienta in resultado.herramientas:
            estado = "ejecutada" if herramienta.ejecutada else "cancelada"
            print(f"  [herramienta] {herramienta.tool_id} ({herramienta.nivel}) — {estado}")

        print(f"ProtexiumAI: {resultado.respuesta}\n")


if __name__ == "__main__":
    main()
