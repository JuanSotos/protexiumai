"""El esquema que ve el LLM solo incluye las herramientas aplicables al equipo, y el agente lo explica.

Complementa a `test_tools_schema.py` y `test_catalogo_regresion.py` (que corren sobre el Windows 11
simulado de conftest) con otros equipos: Windows 10, Linux y un sistema desconocido.
"""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import Mock

import pytest
from openai.types.chat.chat_completion import ChatCompletion, Choice
from openai.types.chat.chat_completion_message import ChatCompletionMessage

from src import catalogo, executor
from src.agent import AVISO_SIN_HERRAMIENTAS, SYSTEM_PROMPT, Agent
from src.config import PerfilLLM
from src.plataforma.deteccion import Capacidades
from src.tools_schema import generar_tools_schema

WIN10_HOME = Capacidades(so="windows", windows_build=19045, windows_edicion="Core")
WIN11_HOME = Capacidades(so="windows", windows_build=26100, windows_edicion="Core")
WIN11_PRO = Capacidades(so="windows", windows_build=26100, windows_edicion="Professional")
UBUNTU = Capacidades(so="linux", linux_id="ubuntu", linux_nombre="Ubuntu", familia="debian")


def nombres(esquema: list[dict]) -> set[str]:
    return {tool["function"]["name"] for tool in esquema}


# --- Esquema por equipo ------------------------------------------------------------------
@pytest.mark.parametrize("caps", [WIN11_HOME, WIN11_PRO, WIN10_HOME])
def test_en_windows_aparecen_las_25_herramientas(caps):
    esquema = generar_tools_schema(caps)

    assert len(esquema) == 25
    assert nombres(esquema) == set(executor.WHITELIST)


def test_el_esquema_por_defecto_usa_el_equipo_detectado():
    # conftest simula un Windows 11 Pro: el esquema por defecto equivale al explícito.
    assert generar_tools_schema() == generar_tools_schema(WIN11_PRO)


@pytest.mark.parametrize("caps", [UBUNTU, Capacidades(so="otro")])
def test_fuera_de_windows_el_esquema_queda_vacio(caps):
    assert generar_tools_schema(caps) == []


def test_el_perfil_sistemas_tambien_ofrece_las_25():
    assert len(generar_tools_schema(WIN11_PRO, perfil="sistemas")) == 25


def test_un_perfil_invalido_es_un_error():
    with pytest.raises(ValueError, match="perfil desconocido"):
        generar_tools_schema(WIN11_PRO, perfil="invitado")


def test_una_herramienta_solo_para_windows_11_desaparece_en_windows_10():
    real = catalogo.cargar_catalogo()
    solo_11 = replace(real.entradas["get_defender_status"], plataforma=catalogo.Plataforma(so="windows", build_min=22000))
    cat = catalogo.Catalogo(entradas={**real.entradas, "get_defender_status": solo_11})

    en_win10 = nombres(generar_tools_schema(WIN10_HOME, cat=cat))
    en_win11 = nombres(generar_tools_schema(WIN11_HOME, cat=cat))

    assert "get_defender_status" not in en_win10
    assert len(en_win10) == 24
    assert "get_defender_status" in en_win11
    assert len(en_win11) == 25


def test_el_filtro_conserva_el_orden_de_la_whitelist():
    esquema = generar_tools_schema(WIN11_PRO)
    assert [t["function"]["name"] for t in esquema] == list(executor.WHITELIST)


# --- Agente ------------------------------------------------------------------------------
def _perfil() -> PerfilLLM:
    return PerfilLLM(proveedor="groq", base_url="https://api.groq.com/openai/v1", api_key="k", modelo="m")


def _cliente_que_responde(texto: str) -> Mock:
    mensaje = ChatCompletionMessage(role="assistant", content=texto, tool_calls=None)
    completion = ChatCompletion(
        id="c", choices=[Choice(finish_reason="stop", index=0, message=mensaje)], created=0, model="m", object="chat.completion"
    )
    cliente = Mock()
    cliente.chat.completions.create = Mock(return_value=completion)
    return cliente


def test_en_linux_el_agente_no_envia_tools_y_lo_explica_en_el_prompt():
    cliente = _cliente_que_responde("Todavía no puedo revisar este equipo.")
    agente = Agent(perfil=_perfil(), cliente=cliente, capacidades=UBUNTU)

    resultado = agente.enviar_mensaje("¿cómo está mi PC?")

    argumentos = cliente.chat.completions.create.call_args.kwargs
    assert "tools" not in argumentos
    prompt = argumentos["messages"][0]["content"]
    assert prompt.startswith(SYSTEM_PROMPT)
    assert "AVISO DE ENTORNO" in prompt
    assert "Linux (Ubuntu)" in prompt
    assert resultado.respuesta == "Todavía no puedo revisar este equipo."
    assert resultado.herramientas == []


def test_en_windows_el_agente_envia_las_tools_y_no_anade_aviso():
    cliente = _cliente_que_responde("Todo bien.")
    agente = Agent(perfil=_perfil(), cliente=cliente, capacidades=WIN11_PRO)

    agente.enviar_mensaje("hola")

    argumentos = cliente.chat.completions.create.call_args.kwargs
    assert len(argumentos["tools"]) == 25
    assert argumentos["messages"][0]["content"] == SYSTEM_PROMPT


def test_el_agente_usa_las_capacidades_detectadas_si_no_se_le_pasan():
    cliente = _cliente_que_responde("ok")
    Agent(perfil=_perfil(), cliente=cliente).enviar_mensaje("hola")

    assert len(cliente.chat.completions.create.call_args.kwargs["tools"]) == 25


def test_el_aviso_no_menciona_usuario_ni_equipo_concreto():
    texto = AVISO_SIN_HERRAMIENTAS.format(sistema="Linux (Ubuntu)")
    assert "Windows 11" in texto and "{" not in texto
