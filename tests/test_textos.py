"""Tests de las tablas de redacción en llano de la interfaz (app/textos.py).

Son tests anti-deriva: la WHITELIST es la única fuente de verdad, así que si
mañana se añade una herramienta o un valor de enum sin su redacción, estos tests
fallan en vez de dejar un tool_id crudo delante del usuario.
"""

from __future__ import annotations

import pytest

from app import textos
from src import executor

FORMAS = ("hecho", "sin_hacer", "en_curso")

# Los siete motivos que emiten src/executor.py y src/agent.py.
MOTIVOS_REALES = (
    "usuario_rechazo",
    "requiere_admin",
    "tool_id_desconocido",
    "parametro_no_declarado",
    "parametro_faltante",
    "valor_fuera_de_enum",
    "argumentos_invalidos",
)


@pytest.mark.parametrize("forma", FORMAS)
def test_todas_las_herramientas_tienen_nombre_en_llano(forma: str) -> None:
    faltan = [tool_id for tool_id in executor.WHITELIST if tool_id not in textos._FORMAS[forma]]
    assert faltan == [], f"herramientas sin redacción en forma '{forma}': {faltan}"


@pytest.mark.parametrize("forma", FORMAS)
def test_ninguna_frase_deja_ver_el_tool_id(forma: str) -> None:
    """El identificador técnico solo aparece en el detalle técnico, nunca en la frase."""
    for tool_id, spec in executor.WHITELIST.items():
        params = {nombre: valores[0] for nombre, valores in spec.parametros.items()}
        frase = textos.frase(tool_id, params, forma)
        assert tool_id not in frase
        assert "{" not in frase, f"campo sin rellenar en {tool_id}: {frase}"


def test_los_valores_de_los_enums_tienen_traduccion_a_llano() -> None:
    valores = {valor for spec in executor.WHITELIST.values() for lista in spec.parametros.values() for valor in lista}
    faltan = sorted(valores - set(textos.VALOR_PLANO))
    assert faltan == [], f"valores de parámetro sin traducir: {faltan}"


def test_los_siete_motivos_de_rechazo_estan_traducidos() -> None:
    assert set(textos.MOTIVO_RECHAZO) == set(MOTIVOS_REALES)
    for texto in textos.MOTIVO_RECHAZO.values():
        assert texto.startswith("Sin hacer · ")


def test_todas_las_acciones_tienen_etiqueta_de_nivel_en_llano() -> None:
    acciones = {t for t, s in executor.WHITELIST.items() if s.nivel != "lectura"}
    assert acciones == set(textos.NIVEL_PLANO)
    assert "accion" not in set(textos.NIVEL_PLANO.values())
    assert "mutante" not in set(textos.NIVEL_PLANO.values())


def test_las_irreversibles_son_mutantes_de_la_whitelist() -> None:
    for tool_id in textos.IRREVERSIBLES:
        assert executor.WHITELIST[tool_id].nivel == "mutante"
        assert tool_id in textos.BOTON_SI
        assert tool_id in textos.ENLACE_ALCANCE
        assert tool_id in textos.NOTA_IRREVERSIBLE


def test_frase_traduce_los_parametros_del_firewall() -> None:
    encendido = textos.frase("set_firewall_profile", {"profile": "Public", "enabled": "True"})
    apagado = textos.frase("set_firewall_profile", {"profile": "Private", "enabled": "False"})
    assert encendido == "He encendido el firewall en redes públicas"
    assert apagado == "He apagado el firewall en red de casa"


def test_frase_en_gerundio_para_el_indicador() -> None:
    assert textos.frase("get_firewall_status", {}, "en_curso") == "Estoy mirando el estado del firewall"
    assert textos.frase("start_custom_scan", {"ruta": "Descargas"}, "en_curso") == (
        "Estoy analizando la carpeta Tu carpeta de Descargas"
    )


def test_frase_de_una_herramienta_desconocida_devuelve_el_identificador() -> None:
    """Si el modelo inventa una herramienta, la interfaz no finge un nombre bonito."""
    assert textos.frase("borrar_disco", {}, "hecho") == "borrar_disco"


def test_alcance_nunca_queda_vacio() -> None:
    """§7: la fila "Sobre qué" existe en las ocho tarjetas, tengan parámetros o no."""
    for tool_id, spec in executor.WHITELIST.items():
        if spec.nivel == "lectura":
            continue
        params = {nombre: valores[0] for nombre, valores in spec.parametros.items()}
        assert textos.alcance(tool_id, params).strip()


def test_se_deshace_dice_que_no_en_las_irreversibles() -> None:
    for tool_id in textos.IRREVERSIBLES:
        _, deshace = textos.consigue_y_deshace(tool_id, {})
        assert deshace.startswith("No.")


def test_el_semaforo_declara_los_cinco_estados() -> None:
    assert set(textos.SEMAFORO) == {"protegido", "atencion", "pasivo", "sin_vigilancia", "sin_dato"}
    # Sin dato no hay vigilancia que representar: las ondas se paran.
    assert textos.SEMAFORO["sin_dato"]["ondas"] is False
    # "Protegido por otro antivirus" no es un fallo: mantiene el verde.
    assert textos.SEMAFORO["pasivo"]["color"] == textos.SEMAFORO["protegido"]["color"]
    assert textos.SEMAFORO["pasivo"]["discontinuo"] is True


def test_el_resultado_sin_datos_cubre_los_trabajos_sin_informe() -> None:
    for tool_id, copia in textos.SIN_DATOS_AL_TERMINAR.items():
        assert executor.WHITELIST[tool_id].nivel == "accion"
        assert copia["boton"] and copia["pregunta"] and copia["titular"]


def test_la_frase_de_no_convergencia_sigue_siendo_la_del_agente(monkeypatch) -> None:
    """§5 · La UI reconoce por su texto el turno que el agente cierra sin converger.

    Si algún día cambia esa frase en src/agent.py, este test lo dice antes de que
    la tarjeta de "Me he liado dando vueltas" deje de aparecer.
    """
    from unittest.mock import Mock

    from openai.types.chat.chat_completion import ChatCompletion, Choice
    from openai.types.chat.chat_completion_message import ChatCompletionMessage
    from openai.types.chat.chat_completion_message_function_tool_call import (
        ChatCompletionMessageFunctionToolCall,
        Function,
    )

    from src.agent import Agent
    from src.config import PerfilLLM

    tool_call = ChatCompletionMessageFunctionToolCall(
        id="call_1", type="function", function=Function(name="get_defender_status", arguments="{}")
    )
    mensaje = ChatCompletionMessage(role="assistant", content=None, tool_calls=[tool_call])
    respuesta = ChatCompletion(
        id="cmpl-1",
        choices=[Choice(finish_reason="tool_calls", index=0, message=mensaje)],
        created=0,
        model="test-model",
        object="chat.completion",
    )
    cliente = Mock()
    cliente.chat.completions.create = Mock(return_value=respuesta)
    monkeypatch.setattr(
        executor,
        "execute",
        lambda tool_id, params, proveedor=None: {
            "ok": True, "tool_id": tool_id, "comando": "c", "timestamp": "t", "duracion_s": 0.1, "data": {}
        },
    )

    perfil = PerfilLLM(proveedor="groq", base_url="https://api.groq.com/openai/v1", api_key="k", modelo="m")
    resultado = Agent(perfil=perfil, cliente=cliente).enviar_mensaje("hola")

    assert resultado.respuesta == textos.RESPUESTA_SIN_CONVERGENCIA


def test_el_titular_de_la_propuesta_habla_en_primera_persona() -> None:
    """README §5 · El titular lo escribe la interfaz; la descripción de la WHITELIST
    está redactada para el modelo, no para el usuario."""
    for tool_id, spec in executor.WHITELIST.items():
        if spec.nivel == "lectura":
            continue
        params = {nombre: valores[0] for nombre, valores in spec.parametros.items()}
        titular = textos.titular_propuesta(tool_id, params, spec.descripcion)
        assert titular.startswith("Voy a "), f"{tool_id}: {titular}"
        assert titular != spec.descripcion
        assert "{" not in titular


def test_el_titular_nombra_la_red_y_el_verbo_correctos() -> None:
    encender = textos.titular_propuesta("set_firewall_profile", {"profile": "Public", "enabled": "True"})
    apagar = textos.titular_propuesta("set_firewall_profile", {"profile": "Public", "enabled": "False"})
    assert encender == "Voy a encender el firewall cuando te conectes a redes públicas"
    assert apagar.startswith("Voy a apagar")


# ---------------------------------------------------------------------------
# Normalización de la respuesta del modelo
# ---------------------------------------------------------------------------

def test_los_br_del_modelo_se_convierten_en_saltos_de_markdown() -> None:
    """El modelo devuelve <br> a veces; st.markdown escapa el HTML y se veían literales."""
    assert textos.limpiar_respuesta("Uno<br>Dos") == "Uno  \nDos"
    assert textos.limpiar_respuesta("Uno<br/>Dos<BR />Tres") == "Uno  \nDos  \nTres"


def test_dentro_de_una_tabla_el_salto_no_rompe_la_fila() -> None:
    """Una celda de Markdown no admite saltos reales: ahí el <br> pasa a separador."""
    fila = "| Defender | Vigilancia activa.<br>Firmas al día. |"
    limpia = textos.limpiar_respuesta(fila)
    assert limpia == "| Defender | Vigilancia activa. · Firmas al día. |"
    assert "\n" not in limpia


def test_una_respuesta_sin_etiquetas_no_se_toca() -> None:
    original = "Tu equipo está bien.\n\nEl firewall está encendido."
    assert textos.limpiar_respuesta(original) == original
    assert textos.limpiar_respuesta("") == ""


def test_la_tabla_completa_sobrevive_a_la_limpieza() -> None:
    tabla = (
        "Resumen:\n"
        "| Tema | Estado |\n"
        "| --- | --- |\n"
        "| Defender | Activado.<br>Al día. |\n"
        "Fin.<br>Gracias."
    )
    limpia = textos.limpiar_respuesta(tabla)
    lineas = limpia.splitlines()
    # Las tres líneas de la tabla siguen siendo tres.
    assert [l for l in lineas if l.startswith("|")] == [
        "| Tema | Estado |",
        "| --- | --- |",
        "| Defender | Activado. · Al día. |",
    ]
    assert "Fin.  " in limpia
