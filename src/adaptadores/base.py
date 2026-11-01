"""Tipos comunes de los adaptadores: la invocación construida, la salida normalizada y la interfaz.

Un adaptador se usa en dos pasos separados a propósito. `construir` es puro: a partir de la
entrada del catálogo y de los parámetros ya validados prepara la `Invocacion`, sin tocar el
sistema. Entre ese paso y `ejecutar`, el executor vuelve a pasar la invocación por la política
(`src/politica.py`), de modo que lo que se comprueba es exactamente lo que se ejecutará.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from src import catalogo

EstadoSalida = Literal["ok", "no_aplicable", "requiere_privilegios", "error"]


@dataclass(frozen=True)
class Invocacion:
    """Lo que un adaptador va a ejecutar, ya construido a partir del catálogo y de valores de enum.

    `texto` es la forma legible que se devuelve en `resultado["comando"]` y se audita. Solo en
    PowerShell coincide con lo que se ejecuta (`-Command <texto>`); en `comando` es argv unido por
    espacios y nunca se pasa a un shell; en `registro` es `HIVE\\ruta\\valor`.
    """

    tool_id: str
    motor: str
    texto: str
    timeout_s: int
    argv: tuple[str, ...] = ()
    clave: catalogo.ClaveRegistro | None = None


@dataclass(frozen=True)
class SalidaAdaptador:
    """Resultado de ejecutar una invocación, con el estado ya normalizado (regla 14)."""

    estado: EstadoSalida
    datos: Any = None
    error: str | None = None


class Adaptador(Protocol):
    """Interfaz común de los adaptadores (un módulo por motor)."""

    MOTOR: str

    def construir(self, entrada: catalogo.Entrada, params: dict[str, str]) -> Invocacion:
        """Prepara la invocación sin efectos sobre el sistema."""
        ...

    def ejecutar(self, invocacion: Invocacion) -> SalidaAdaptador:
        """Ejecuta la invocación y devuelve la salida normalizada; nunca lanza por un binario ausente."""
        ...
