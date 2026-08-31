"""Tests del envoltorio que cuenta la cola de órdenes de un turno (§8).

El envoltorio solo mira: no debe alterar la respuesta del modelo, ni los
argumentos con que el agente llama al cliente, ni romper el turno si la respuesta
llega con una forma inesperada.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.cliente_observado import ClienteObservado


def _tool_call(nombre: str) -> SimpleNamespace:
    return SimpleNamespace(function=SimpleNamespace(name=nombre, arguments="{}"), id=f"id_{nombre}")


def _respuesta(nombres: list[str] | None) -> SimpleNamespace:
    llamadas = [_tool_call(n) for n in nombres] if nombres is not None else None
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=llamadas, content="hola"))])


class _CompletionsFalsas:
    def __init__(self, respuesta: Any) -> None:
        self.respuesta = respuesta
        self.recibido: dict[str, Any] | None = None

    def create(self, **kwargs: Any) -> Any:
        self.recibido = kwargs
        return self.respuesta


class _ClienteFalso:
    def __init__(self, respuesta: Any) -> None:
        self.chat = SimpleNamespace(completions=_CompletionsFalsas(respuesta))
        self.api_key = "sk-de-prueba"


def _envolver(respuesta: Any) -> tuple[ClienteObservado, list]:
    lotes: list = []
    cliente = _ClienteFalso(respuesta)
    return ClienteObservado(cliente, lotes.append), lotes


def test_cuenta_solo_las_herramientas_que_piden_permiso() -> None:
    respuesta = _respuesta(["get_defender_status", "set_firewall_profile", "remove_all_threats"])
    cliente, lotes = _envolver(respuesta)

    cliente.chat.completions.create(model="x", messages=[])

    assert len(lotes) == 1
    assert lotes[0].herramientas == ["get_defender_status", "set_firewall_profile", "remove_all_threats"]
    assert lotes[0].ordenes == ["set_firewall_profile", "remove_all_threats"]
    assert lotes[0].total_ordenes == 2


def test_un_turno_de_solo_lecturas_no_tiene_cola() -> None:
    cliente, lotes = _envolver(_respuesta(["get_defender_status", "get_firewall_status"]))
    cliente.chat.completions.create(model="x", messages=[])
    assert lotes[0].total_ordenes == 0


def test_una_herramienta_fuera_de_la_whitelist_no_cuenta_como_orden() -> None:
    """Si el modelo inventa un nombre, el executor lo rechazará: aquí no se anticipa."""
    cliente, lotes = _envolver(_respuesta(["borrar_disco"]))
    cliente.chat.completions.create(model="x", messages=[])
    assert lotes[0].herramientas == ["borrar_disco"]
    assert lotes[0].ordenes == []


def test_devuelve_la_respuesta_intacta_y_pasa_los_argumentos_tal_cual() -> None:
    respuesta = _respuesta(["get_defender_status"])
    cliente, _ = _envolver(respuesta)

    devuelta = cliente.chat.completions.create(model="llama", messages=[{"role": "user", "content": "hola"}], tools=[])

    assert devuelta is respuesta
    recibido = cliente._cliente.chat.completions.recibido
    assert recibido["model"] == "llama"
    assert recibido["messages"] == [{"role": "user", "content": "hola"}]
    assert recibido["tools"] == []


def test_una_respuesta_sin_tool_calls_da_un_lote_vacio() -> None:
    cliente, lotes = _envolver(_respuesta(None))
    cliente.chat.completions.create(model="x", messages=[])
    assert lotes[0].herramientas == []


def test_una_respuesta_con_forma_inesperada_no_rompe_el_turno() -> None:
    cliente, lotes = _envolver(SimpleNamespace(choices=[]))
    devuelta = cliente.chat.completions.create(model="x", messages=[])
    assert devuelta is not None
    assert lotes[0].herramientas == []


def test_un_observador_que_falla_no_rompe_el_turno() -> None:
    def observador_roto(_lote):
        raise RuntimeError("fallo del observador")

    respuesta = _respuesta(["get_defender_status"])
    cliente = ClienteObservado(_ClienteFalso(respuesta), observador_roto)
    assert cliente.chat.completions.create(model="x", messages=[]) is respuesta


def test_el_resto_de_la_api_del_cliente_se_delega() -> None:
    cliente, _ = _envolver(_respuesta([]))
    assert cliente.api_key == "sk-de-prueba"
