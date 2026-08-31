"""Envoltorio de solo lectura del cliente LLM, para saber cuántas órdenes trae un turno.

`Agent` decide y ejecuta exactamente igual que siempre: este objeto se limita a
mirar la respuesta del modelo antes de devolvérsela intacta, y a contar cuántas de
las herramientas del lote son de nivel `accion` o `mutante`. De ahí sale el
"Orden 1 de 3" de la tarjeta de permiso y de la barra lateral (ADDENDUM-02 §8),
sin tocar `src/agent.py`.

Se inyecta por el mismo punto que ya existe en `Agent.__init__(cliente=...)`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from src import executor


@dataclass(frozen=True)
class Lote:
    """Las herramientas que el modelo ha pedido en una sola respuesta."""

    herramientas: list[str] = field(default_factory=list)
    ordenes: list[str] = field(default_factory=list)

    @property
    def total_ordenes(self) -> int:
        return len(self.ordenes)


ObservadorLote = Callable[[Lote], None]


def _leer_lote(respuesta: Any) -> Lote:
    """Extrae los tool_id de una respuesta del LLM sin asumir que vengan bien formados."""
    try:
        mensaje = respuesta.choices[0].message
        llamadas = mensaje.tool_calls or []
        herramientas = [str(c.function.name) for c in llamadas]
    except (AttributeError, IndexError, TypeError):
        return Lote()
    ordenes = [
        tool_id
        for tool_id in herramientas
        if (spec := executor.WHITELIST.get(tool_id)) is not None and spec.nivel != "lectura"
    ]
    return Lote(herramientas=herramientas, ordenes=ordenes)


class _Completions:
    def __init__(self, real: Any, observador: ObservadorLote) -> None:
        self._real = real
        self._observador = observador

    def create(self, **kwargs: Any) -> Any:
        respuesta = self._real.create(**kwargs)
        try:
            self._observador(_leer_lote(respuesta))
        except Exception:  # noqa: BLE001 — observar nunca puede romper el turno
            pass
        return respuesta


class _Chat:
    def __init__(self, real: Any, observador: ObservadorLote) -> None:
        self.completions = _Completions(real.completions, observador)


class ClienteObservado:
    """Cliente compatible con el SDK de OpenAI que avisa de cada lote de herramientas."""

    def __init__(self, cliente: Any, observador: ObservadorLote) -> None:
        self._cliente = cliente
        self.chat = _Chat(cliente.chat, observador)

    def __getattr__(self, nombre: str) -> Any:
        # Cualquier otra parte de la API del cliente se delega sin modificar.
        return getattr(self._cliente, nombre)
