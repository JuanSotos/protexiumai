"""Tests de src/agent.py: bucle de function calling, confirmación humana y auditoría de cancelaciones.

El cliente OpenAI se inyecta por constructor (nunca hay llamadas de red real).
executor.execute se mockea con monkeypatch en cada test; solo el test de
cancelación deja que la auditoría real escriba en el log (vía la fixture
autouse ruta_audit_temporal de conftest.py) para verificar la integración.
"""

from __future__ import annotations

import json
from unittest.mock import Mock

from openai.types.chat.chat_completion import ChatCompletion, Choice
from openai.types.chat.chat_completion_message import ChatCompletionMessage
from openai.types.chat.chat_completion_message_function_tool_call import (
    ChatCompletionMessageFunctionToolCall,
    Function,
)

from src import executor
from src.agent import MAX_ITERACIONES_POR_TURNO, Agent
from src.config import PerfilLLM


def _perfil() -> PerfilLLM:
    return PerfilLLM(proveedor="groq", base_url="https://api.groq.com/openai/v1", api_key="k", modelo="m")


def _tool_call(id_: str, name: str, arguments: str) -> ChatCompletionMessageFunctionToolCall:
    return ChatCompletionMessageFunctionToolCall(id=id_, type="function", function=Function(name=name, arguments=arguments))


def _completion_con_tool_calls(tool_calls: list[ChatCompletionMessageFunctionToolCall]) -> ChatCompletion:
    mensaje = ChatCompletionMessage(role="assistant", content=None, tool_calls=tool_calls)
    choice = Choice(finish_reason="tool_calls", index=0, message=mensaje)
    return ChatCompletion(id="cmpl-1", choices=[choice], created=0, model="test-model", object="chat.completion")


def _completion_final(texto: str) -> ChatCompletion:
    mensaje = ChatCompletionMessage(role="assistant", content=texto, tool_calls=None)
    choice = Choice(finish_reason="stop", index=0, message=mensaje)
    return ChatCompletion(id="cmpl-2", choices=[choice], created=0, model="test-model", object="chat.completion")


def _resultado_ok(tool_id: str) -> dict:
    return {"ok": True, "tool_id": tool_id, "comando": "c", "timestamp": "t", "duracion_s": 0.1, "data": {}}


def _leer_lineas_audit(ruta_audit_temporal) -> list[dict]:
    if not ruta_audit_temporal.exists():
        return []
    return [json.loads(linea) for linea in ruta_audit_temporal.read_text(encoding="utf-8").splitlines() if linea.strip()]


def test_tool_lectura_se_ejecuta_sin_pedir_confirmacion(monkeypatch):
    tool_call = _tool_call("call_1", "get_defender_status", "{}")
    cliente = Mock()
    cliente.chat.completions.create = Mock(
        side_effect=[_completion_con_tool_calls([tool_call]), _completion_final("Tu Defender está bien.")]
    )
    mock_execute = Mock(return_value=_resultado_ok("get_defender_status"))
    monkeypatch.setattr(executor, "execute", mock_execute)
    confirmar = Mock()

    agente = Agent(perfil=_perfil(), confirmar=confirmar, cliente=cliente)
    resultado = agente.enviar_mensaje("¿cómo está mi PC?")

    mock_execute.assert_called_once_with("get_defender_status", {}, proveedor="groq")
    confirmar.assert_not_called()
    assert resultado.respuesta == "Tu Defender está bien."
    assert resultado.herramientas[0].ejecutada is True
    assert resultado.herramientas[0].ok is True


def test_tool_mutante_con_confirmacion_true_se_ejecuta(monkeypatch):
    tool_call = _tool_call("call_1", "start_quick_scan", "{}")
    cliente = Mock()
    cliente.chat.completions.create = Mock(
        side_effect=[_completion_con_tool_calls([tool_call]), _completion_final("Escaneo iniciado.")]
    )
    mock_execute = Mock(return_value=_resultado_ok("start_quick_scan"))
    monkeypatch.setattr(executor, "execute", mock_execute)
    confirmar = Mock(return_value=True)

    agente = Agent(perfil=_perfil(), confirmar=confirmar, cliente=cliente)
    resultado = agente.enviar_mensaje("hazme un escaneo rápido")

    confirmar.assert_called_once_with(
        "start_quick_scan", executor.WHITELIST["start_quick_scan"].descripcion, {}
    )
    mock_execute.assert_called_once_with("start_quick_scan", {}, proveedor="groq")
    assert resultado.herramientas[0].ejecutada is True


def test_tool_mutante_con_confirmacion_false_no_ejecuta_y_audita(monkeypatch, ruta_audit_temporal):
    tool_call = _tool_call("call_1", "set_firewall_profile", '{"profile": "Private", "enabled": "True"}')
    cliente = Mock()
    cliente.chat.completions.create = Mock(
        side_effect=[_completion_con_tool_calls([tool_call]), _completion_final("De acuerdo, no he cambiado nada.")]
    )
    mock_execute = Mock()
    monkeypatch.setattr(executor, "execute", mock_execute)
    confirmar = Mock(return_value=False)
    perfil = _perfil()

    agente = Agent(perfil=perfil, confirmar=confirmar, cliente=cliente)
    resultado = agente.enviar_mensaje("desactiva el firewall privado")

    mock_execute.assert_not_called()
    assert resultado.herramientas[0].ejecutada is False
    assert resultado.herramientas[0].ok is False

    lineas = _leer_lineas_audit(ruta_audit_temporal)
    assert len(lineas) == 1
    assert lineas[0]["tool_id"] == "set_firewall_profile"
    assert lineas[0]["motivo_rechazo"] == "usuario_rechazo"
    assert lineas[0]["proveedor"] == perfil.proveedor
    assert lineas[0]["resultado"]["ok"] is False


def test_tool_start_full_scan_con_confirmacion_true_se_ejecuta(monkeypatch):
    tool_call = _tool_call("call_1", "start_full_scan", "{}")
    cliente = Mock()
    cliente.chat.completions.create = Mock(
        side_effect=[_completion_con_tool_calls([tool_call]), _completion_final("Análisis completo iniciado.")]
    )
    mock_execute = Mock(return_value=_resultado_ok("start_full_scan"))
    monkeypatch.setattr(executor, "execute", mock_execute)
    confirmar = Mock(return_value=True)

    agente = Agent(perfil=_perfil(), confirmar=confirmar, cliente=cliente)
    resultado = agente.enviar_mensaje("hazme un análisis completo")

    confirmar.assert_called_once_with(
        "start_full_scan", executor.WHITELIST["start_full_scan"].descripcion, {}
    )
    mock_execute.assert_called_once_with("start_full_scan", {}, proveedor="groq")
    assert resultado.herramientas[0].ejecutada is True


def test_tool_start_full_scan_con_confirmacion_false_no_ejecuta_y_audita(monkeypatch, ruta_audit_temporal):
    tool_call = _tool_call("call_1", "start_full_scan", "{}")
    cliente = Mock()
    cliente.chat.completions.create = Mock(
        side_effect=[_completion_con_tool_calls([tool_call]), _completion_final("De acuerdo, no lo inicio.")]
    )
    mock_execute = Mock()
    monkeypatch.setattr(executor, "execute", mock_execute)
    confirmar = Mock(return_value=False)
    perfil = _perfil()

    agente = Agent(perfil=perfil, confirmar=confirmar, cliente=cliente)
    resultado = agente.enviar_mensaje("hazme un análisis completo")

    mock_execute.assert_not_called()
    assert resultado.herramientas[0].ejecutada is False
    assert resultado.herramientas[0].ok is False

    lineas = _leer_lineas_audit(ruta_audit_temporal)
    assert len(lineas) == 1
    assert lineas[0]["tool_id"] == "start_full_scan"
    assert lineas[0]["motivo_rechazo"] == "usuario_rechazo"
    assert lineas[0]["proveedor"] == perfil.proveedor
    assert lineas[0]["resultado"]["ok"] is False


def test_tool_start_custom_scan_con_confirmacion_true_se_ejecuta(monkeypatch):
    tool_call = _tool_call("call_1", "start_custom_scan", '{"ruta": "Descargas"}')
    cliente = Mock()
    cliente.chat.completions.create = Mock(
        side_effect=[_completion_con_tool_calls([tool_call]), _completion_final("Análisis de Descargas iniciado.")]
    )
    mock_execute = Mock(return_value=_resultado_ok("start_custom_scan"))
    monkeypatch.setattr(executor, "execute", mock_execute)
    confirmar = Mock(return_value=True)

    agente = Agent(perfil=_perfil(), confirmar=confirmar, cliente=cliente)
    resultado = agente.enviar_mensaje("analiza mi carpeta de Descargas")

    confirmar.assert_called_once_with(
        "start_custom_scan", executor.WHITELIST["start_custom_scan"].descripcion, {"ruta": "Descargas"}
    )
    mock_execute.assert_called_once_with("start_custom_scan", {"ruta": "Descargas"}, proveedor="groq")
    assert resultado.herramientas[0].ejecutada is True


def test_tool_start_custom_scan_con_confirmacion_false_no_ejecuta_y_audita(monkeypatch, ruta_audit_temporal):
    tool_call = _tool_call("call_1", "start_custom_scan", '{"ruta": "Descargas"}')
    cliente = Mock()
    cliente.chat.completions.create = Mock(
        side_effect=[_completion_con_tool_calls([tool_call]), _completion_final("De acuerdo, no lo inicio.")]
    )
    mock_execute = Mock()
    monkeypatch.setattr(executor, "execute", mock_execute)
    confirmar = Mock(return_value=False)
    perfil = _perfil()

    agente = Agent(perfil=perfil, confirmar=confirmar, cliente=cliente)
    resultado = agente.enviar_mensaje("analiza mi carpeta de Descargas")

    mock_execute.assert_not_called()
    assert resultado.herramientas[0].ejecutada is False
    assert resultado.herramientas[0].ok is False

    lineas = _leer_lineas_audit(ruta_audit_temporal)
    assert len(lineas) == 1
    assert lineas[0]["tool_id"] == "start_custom_scan"
    assert lineas[0]["motivo_rechazo"] == "usuario_rechazo"
    assert lineas[0]["proveedor"] == perfil.proveedor
    assert lineas[0]["resultado"]["ok"] is False


def test_tool_set_block_all_incoming_con_confirmacion_true_se_ejecuta(monkeypatch):
    tool_call = _tool_call(
        "call_1", "set_block_all_incoming", '{"profile": "Private", "allow_inbound_rules": "False"}'
    )
    cliente = Mock()
    cliente.chat.completions.create = Mock(
        side_effect=[_completion_con_tool_calls([tool_call]), _completion_final("Entrantes bloqueadas.")]
    )
    mock_execute = Mock(return_value=_resultado_ok("set_block_all_incoming"))
    monkeypatch.setattr(executor, "execute", mock_execute)
    confirmar = Mock(return_value=True)

    agente = Agent(perfil=_perfil(), confirmar=confirmar, cliente=cliente)
    resultado = agente.enviar_mensaje("bloquea todas las conexiones entrantes en la red privada")

    confirmar.assert_called_once_with(
        "set_block_all_incoming",
        executor.WHITELIST["set_block_all_incoming"].descripcion,
        {"profile": "Private", "allow_inbound_rules": "False"},
    )
    mock_execute.assert_called_once_with(
        "set_block_all_incoming",
        {"profile": "Private", "allow_inbound_rules": "False"},
        proveedor="groq",
    )
    assert resultado.herramientas[0].ejecutada is True


def test_tool_set_block_all_incoming_con_confirmacion_false_no_ejecuta_y_audita(monkeypatch, ruta_audit_temporal):
    tool_call = _tool_call(
        "call_1", "set_block_all_incoming", '{"profile": "Private", "allow_inbound_rules": "False"}'
    )
    cliente = Mock()
    cliente.chat.completions.create = Mock(
        side_effect=[_completion_con_tool_calls([tool_call]), _completion_final("De acuerdo, no he cambiado nada.")]
    )
    mock_execute = Mock()
    monkeypatch.setattr(executor, "execute", mock_execute)
    confirmar = Mock(return_value=False)
    perfil = _perfil()

    agente = Agent(perfil=perfil, confirmar=confirmar, cliente=cliente)
    resultado = agente.enviar_mensaje("bloquea todas las conexiones entrantes en la red privada")

    mock_execute.assert_not_called()
    assert resultado.herramientas[0].ejecutada is False
    assert resultado.herramientas[0].ok is False

    lineas = _leer_lineas_audit(ruta_audit_temporal)
    assert len(lineas) == 1
    assert lineas[0]["tool_id"] == "set_block_all_incoming"
    assert lineas[0]["motivo_rechazo"] == "usuario_rechazo"
    assert lineas[0]["proveedor"] == perfil.proveedor
    assert lineas[0]["resultado"]["ok"] is False


def test_tool_restore_firewall_defaults_con_confirmacion_true_se_ejecuta(monkeypatch):
    tool_call = _tool_call("call_1", "restore_firewall_defaults", "{}")
    cliente = Mock()
    cliente.chat.completions.create = Mock(
        side_effect=[_completion_con_tool_calls([tool_call]), _completion_final("Firewall restaurado.")]
    )
    mock_execute = Mock(return_value=_resultado_ok("restore_firewall_defaults"))
    monkeypatch.setattr(executor, "execute", mock_execute)
    confirmar = Mock(return_value=True)

    agente = Agent(perfil=_perfil(), confirmar=confirmar, cliente=cliente)
    resultado = agente.enviar_mensaje("restaura el firewall a los valores de fábrica")

    confirmar.assert_called_once_with(
        "restore_firewall_defaults", executor.WHITELIST["restore_firewall_defaults"].descripcion, {}
    )
    mock_execute.assert_called_once_with("restore_firewall_defaults", {}, proveedor="groq")
    assert resultado.herramientas[0].ejecutada is True


def test_tool_restore_firewall_defaults_con_confirmacion_false_no_ejecuta_y_audita(monkeypatch, ruta_audit_temporal):
    tool_call = _tool_call("call_1", "restore_firewall_defaults", "{}")
    cliente = Mock()
    cliente.chat.completions.create = Mock(
        side_effect=[_completion_con_tool_calls([tool_call]), _completion_final("De acuerdo, no lo restauro.")]
    )
    mock_execute = Mock()
    monkeypatch.setattr(executor, "execute", mock_execute)
    confirmar = Mock(return_value=False)
    perfil = _perfil()

    agente = Agent(perfil=perfil, confirmar=confirmar, cliente=cliente)
    resultado = agente.enviar_mensaje("restaura el firewall a los valores de fábrica")

    mock_execute.assert_not_called()
    assert resultado.herramientas[0].ejecutada is False
    assert resultado.herramientas[0].ok is False

    lineas = _leer_lineas_audit(ruta_audit_temporal)
    assert len(lineas) == 1
    assert lineas[0]["tool_id"] == "restore_firewall_defaults"
    assert lineas[0]["motivo_rechazo"] == "usuario_rechazo"
    assert lineas[0]["proveedor"] == perfil.proveedor
    assert lineas[0]["resultado"]["ok"] is False


def test_argumentos_invalidos_no_llama_a_execute_y_continua(monkeypatch, ruta_audit_temporal):
    tool_call = _tool_call("call_1", "get_defender_status", "{esto no es json")
    cliente = Mock()
    cliente.chat.completions.create = Mock(
        side_effect=[_completion_con_tool_calls([tool_call]), _completion_final("No he podido consultar el estado.")]
    )
    mock_execute = Mock()
    monkeypatch.setattr(executor, "execute", mock_execute)

    agente = Agent(perfil=_perfil(), cliente=cliente)
    resultado = agente.enviar_mensaje("¿cómo está mi PC?")

    mock_execute.assert_not_called()
    assert resultado.herramientas[0].ejecutada is False

    lineas = _leer_lineas_audit(ruta_audit_temporal)
    assert len(lineas) == 1
    assert lineas[0]["motivo_rechazo"] == "argumentos_invalidos"


def test_tool_id_alucinado_delega_en_executor_execute(monkeypatch):
    tool_call = _tool_call("call_1", "borrar_disco", "{}")
    cliente = Mock()
    cliente.chat.completions.create = Mock(
        side_effect=[_completion_con_tool_calls([tool_call]), _completion_final("Esa herramienta no existe.")]
    )
    mock_execute = Mock(
        return_value={
            "ok": False,
            "tool_id": "borrar_disco",
            "comando": None,
            "timestamp": "t",
            "duracion_s": 0.0,
            "error": "Herramienta desconocida: 'borrar_disco'.",
        }
    )
    monkeypatch.setattr(executor, "execute", mock_execute)
    confirmar = Mock()

    agente = Agent(perfil=_perfil(), confirmar=confirmar, cliente=cliente)
    agente.enviar_mensaje("borra el disco")

    mock_execute.assert_called_once_with("borrar_disco", {}, proveedor="groq")
    confirmar.assert_not_called()


def test_limite_de_iteraciones_devuelve_respuesta_de_disculpa(monkeypatch):
    tool_call = _tool_call("call_1", "get_defender_status", "{}")
    cliente = Mock()
    cliente.chat.completions.create = Mock(return_value=_completion_con_tool_calls([tool_call]))
    monkeypatch.setattr(executor, "execute", Mock(return_value=_resultado_ok("get_defender_status")))

    agente = Agent(perfil=_perfil(), cliente=cliente)
    resultado = agente.enviar_mensaje("¿cómo está mi PC?")

    assert "reformula" in resultado.respuesta.lower()
    assert cliente.chat.completions.create.call_count == MAX_ITERACIONES_POR_TURNO


def test_varias_tool_calls_en_un_turno_generan_un_resultado_por_cada_una(monkeypatch):
    tool_call_1 = _tool_call("call_1", "get_defender_status", "{}")
    tool_call_2 = _tool_call("call_2", "get_firewall_status", "{}")
    cliente = Mock()
    cliente.chat.completions.create = Mock(
        side_effect=[_completion_con_tool_calls([tool_call_1, tool_call_2]), _completion_final("Todo en orden.")]
    )
    mock_execute = Mock(side_effect=[_resultado_ok("get_defender_status"), _resultado_ok("get_firewall_status")])
    monkeypatch.setattr(executor, "execute", mock_execute)

    agente = Agent(perfil=_perfil(), cliente=cliente)
    resultado = agente.enviar_mensaje("¿cómo está mi PC?")

    assert mock_execute.call_count == 2
    assert {h.tool_id for h in resultado.herramientas} == {"get_defender_status", "get_firewall_status"}

    segunda_llamada = cliente.chat.completions.create.call_args_list[1]
    mensajes_enviados = segunda_llamada.kwargs["messages"]
    mensajes_tool = [m for m in mensajes_enviados if m.get("role") == "tool"]
    assert len(mensajes_tool) == 2
    assert {m["tool_call_id"] for m in mensajes_tool} == {"call_1", "call_2"}


def test_sin_callback_confirmar_deniega_por_defecto(monkeypatch):
    tool_call = _tool_call("call_1", "remove_all_threats", "{}")
    cliente = Mock()
    cliente.chat.completions.create = Mock(
        side_effect=[_completion_con_tool_calls([tool_call]), _completion_final("No se ha eliminado nada.")]
    )
    mock_execute = Mock()
    monkeypatch.setattr(executor, "execute", mock_execute)

    agente = Agent(perfil=_perfil(), cliente=cliente)
    resultado = agente.enviar_mensaje("elimina todas las amenazas")

    mock_execute.assert_not_called()
    assert resultado.herramientas[0].ejecutada is False
