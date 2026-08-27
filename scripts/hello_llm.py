"""Script de verificación de la conexión con el proveedor LLM configurado (groq/ollama)."""

import os
import sys

from dotenv import load_dotenv
from openai import APIConnectionError, APIError, AuthenticationError, OpenAI

sys.stdout.reconfigure(encoding="utf-8")

BASE_URL = "https://api.groq.com/openai/v1"
MODEL = "llama-3.3-70b-versatile"
PREGUNTA = "Responde en una frase: ¿estás operativo?"


def main() -> None:
    load_dotenv()

    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        print(
            "Error: no se ha encontrado GROQ_API_KEY.\n"
            "Copia .env.example a .env y rellena GROQ_API_KEY con tu clave de Groq.",
            file=sys.stderr,
        )
        sys.exit(1)

    cliente = OpenAI(base_url=BASE_URL, api_key=api_key)

    try:
        respuesta = cliente.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": PREGUNTA}],
        )
    except AuthenticationError:
        print(
            "Error: la API key de Groq no es válida. Revisa GROQ_API_KEY en .env.",
            file=sys.stderr,
        )
        sys.exit(1)
    except APIConnectionError:
        print(
            "Error: no se ha podido conectar con la API de Groq. Comprueba tu conexión a internet.",
            file=sys.stderr,
        )
        sys.exit(1)
    except APIError as error:
        print(f"Error al llamar a la API de Groq: {error}", file=sys.stderr)
        sys.exit(1)

    print(respuesta.choices[0].message.content)


if __name__ == "__main__":
    main()
