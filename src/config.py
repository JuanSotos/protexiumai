"""Carga de variables de entorno (.env) y definición de los perfiles de proveedor LLM (groq/ollama)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
# NOTA: CLAUDE.md especifica "llama-3.3-70b-versatile", pero Groq lo retiró de
# su catálogo. "openai/gpt-oss-120b" (la alternativa más comparable) supera el
# límite de tokens por minuto del tier gratuito de esta cuenta con el tamaño
# de prompt de ProtexiumAI (~8.6k tokens); "openai/gpt-oss-20b" sí entra.
GROQ_MODELO = "openai/gpt-oss-20b"

OLLAMA_BASE_URL_DEFECTO = "http://localhost:11434/v1"
OLLAMA_MODELO_DEFECTO = "llama3.2:3b"
OLLAMA_API_KEY = "ollama"


@dataclass(frozen=True)
class PerfilLLM:
    """Perfil de conexión al proveedor LLM activo, compatible con el SDK de OpenAI."""

    proveedor: str
    base_url: str
    api_key: str
    modelo: str


def cargar_perfil() -> PerfilLLM:
    """Carga .env y devuelve el perfil del proveedor LLM activo según LLM_PROVIDER."""
    load_dotenv()

    proveedor = os.environ.get("LLM_PROVIDER", "groq").strip().lower()

    if proveedor == "groq":
        return PerfilLLM(
            proveedor="groq",
            base_url=GROQ_BASE_URL,
            api_key=os.environ.get("GROQ_API_KEY", "").strip(),
            modelo=GROQ_MODELO,
        )

    if proveedor == "ollama":
        return PerfilLLM(
            proveedor="ollama",
            base_url=os.environ.get("LLM_BASE_URL", OLLAMA_BASE_URL_DEFECTO).strip(),
            api_key=OLLAMA_API_KEY,
            modelo=os.environ.get("LLM_MODEL", OLLAMA_MODELO_DEFECTO).strip(),
        )

    raise ValueError(
        f"Proveedor LLM desconocido: '{proveedor}'. Valores admitidos: 'groq', 'ollama'."
    )
