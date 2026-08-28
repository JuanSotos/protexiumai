"""Script de verificación del modo privado (Ollama): comprueba conectividad y que el modelo esté descargado."""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openai import APIConnectionError, APIError, OpenAI  # noqa: E402

from src.config import cargar_perfil  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


def main() -> None:
    # Se fuerza el proveedor "ollama" para comprobar el modo privado
    # independientemente de qué proveedor tenga activo el .env actual, pero
    # respetando LLM_MODEL/LLM_BASE_URL si el usuario los ha personalizado.
    os.environ["LLM_PROVIDER"] = "ollama"
    perfil = cargar_perfil()

    cliente = OpenAI(base_url=perfil.base_url, api_key=perfil.api_key)

    try:
        respuesta = cliente.models.list()
    except APIConnectionError:
        print(
            f"Error: no se ha podido conectar con Ollama en {perfil.base_url}.\n"
            "Comprueba que esté en marcha: `ollama serve`.",
            file=sys.stderr,
        )
        sys.exit(1)
    except APIError as error:
        print(f"Error al consultar Ollama: {error}", file=sys.stderr)
        sys.exit(1)

    modelos_disponibles = {modelo.id for modelo in respuesta.data}
    if perfil.modelo not in modelos_disponibles:
        print(
            f"Error: el modelo '{perfil.modelo}' no está descargado en Ollama.\n"
            f"Descárgalo con: ollama pull {perfil.modelo}\n"
            f"Modelos disponibles: {sorted(modelos_disponibles) or '(ninguno)'}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(f"Modo privado listo: Ollama responde en {perfil.base_url} y '{perfil.modelo}' está descargado.")


if __name__ == "__main__":
    main()
