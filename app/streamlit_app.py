"""Interfaz gráfica de ProtexiumAI construida con Streamlit."""

from __future__ import annotations

import os
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# `streamlit run` coloca el directorio del propio script (app/) en sys.path,
# no la raíz del repositorio: hay que añadirla a mano para poder importar src.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from openai import APIConnectionError, APIError, AuthenticationError

from src import executor
from src.agent import Agent, ResultadoTurno
from src.config import PerfilLLM, cargar_perfil

st.set_page_config(page_title="ProtexiumAI", page_icon="🛡️", layout="centered")

PROVEEDORES = {"Nube (Groq)": "groq", "Local (Ollama)": "ollama"}
NOTA_PRIVACIDAD = {
    "groq": "🌐 Modo nube activo: las consultas se procesan en servidores de Groq.",
    "ollama": "🔒 Modo local activo: nada sale de este equipo.",
}
ETIQUETA_NIVEL = {"accion": "⚠️ Acción", "mutante": "🔴 Mutante", "desconocido": "❔"}


@dataclass
class EstadoTurno:
    """Estado compartido entre el hilo trabajador (agente) y el hilo principal (Streamlit) para un turno."""

    evento_decision: threading.Event = field(default_factory=threading.Event)
    propuesta: dict[str, Any] | None = None
    decision: bool | None = None
    resultado: ResultadoTurno | None = None
    error: Exception | None = None
    terminado: bool = False


def _confirmar(contenedor_estado: dict[str, EstadoTurno | None], tool_id: str, descripcion: str, params: dict[str, Any]) -> bool:
    """Callback de confirmación pasado al Agent: publica la propuesta y bloquea el hilo trabajador.

    Se ejecuta dentro del hilo en segundo plano lanzado por _ejecutar_turno. Publica la
    propuesta en el EstadoTurno activo y espera a que el hilo principal (tras el clic
    del usuario en Confirmar/Cancelar) marque evento_decision.
    """
    estado = contenedor_estado["actual"]
    assert estado is not None
    spec = executor.WHITELIST.get(tool_id)
    estado.propuesta = {
        "tool_id": tool_id,
        "descripcion": descripcion,
        "params": params,
        "nivel": spec.nivel if spec is not None else "desconocido",
    }
    estado.evento_decision.clear()
    estado.evento_decision.wait()
    decision = estado.decision
    estado.propuesta = None
    return bool(decision)


def _ejecutar_turno(agente: Agent, mensaje: str, estado: EstadoTurno) -> None:
    """Función objetivo del hilo trabajador: llama al agente y vuelca el resultado en estado."""
    try:
        estado.resultado = agente.enviar_mensaje(mensaje)
    except Exception as error:  # noqa: BLE001 — se reporta en la UI, no se deja escapar al hilo
        estado.error = error
    finally:
        estado.terminado = True


def _construir_perfil(codigo_proveedor: str) -> PerfilLLM:
    """Construye el PerfilLLM del proveedor elegido reutilizando cargar_perfil() de src/config.py."""
    os.environ["LLM_PROVIDER"] = codigo_proveedor
    return cargar_perfil()


def _inicializar_estado() -> None:
    st.session_state.setdefault("historial_ui", [])
    st.session_state.setdefault("proveedor_actual", None)
    st.session_state.setdefault("agente", None)
    st.session_state.setdefault("hilo", None)
    st.session_state.setdefault("contenedor_estado", {"actual": None})
    st.session_state.setdefault("estado_defender", None)
    st.session_state.setdefault("estado_firewall", None)


def _asegurar_agente(codigo_proveedor: str) -> None:
    """Crea (o recrea al cambiar de proveedor) la instancia de Agent, sin tocar su lógica interna."""
    if st.session_state["agente"] is not None and st.session_state["proveedor_actual"] == codigo_proveedor:
        return
    contenedor_estado = st.session_state["contenedor_estado"]
    try:
        perfil = _construir_perfil(codigo_proveedor)
        st.session_state["agente"] = Agent(
            perfil=perfil,
            confirmar=lambda tool_id, descripcion, params: _confirmar(contenedor_estado, tool_id, descripcion, params),
        )
        st.session_state["proveedor_actual"] = codigo_proveedor
    except ValueError as error:
        st.session_state["agente"] = None
        st.error(f"Error de configuración del proveedor LLM: {error}")


def _calcular_semaforo() -> tuple[str, str, dict[str, Any], dict[str, Any]]:
    """Consulta Defender y firewall directamente (herramientas de lectura) y deriva un color/mensaje."""
    defender = executor.execute("get_defender_status", {})
    firewall = executor.execute("get_firewall_status", {})

    if not defender["ok"] or not firewall["ok"]:
        detalle = defender.get("error") or firewall.get("error") or "No se pudo consultar el estado."
        return "🔴", f"No se pudo comprobar el estado: {detalle}", defender, firewall

    datos_defender = defender["data"] or {}
    datos_firewall = firewall["data"]
    perfiles = datos_firewall if isinstance(datos_firewall, list) else [datos_firewall]
    todos_activos = all(p.get("Enabled") for p in perfiles)

    proteccion_tiempo_real = bool(datos_defender.get("RealTimeProtectionEnabled"))
    antivirus_activo = bool(datos_defender.get("AntivirusEnabled"))
    servicio_activo = bool(datos_defender.get("AMServiceEnabled"))

    if antivirus_activo and proteccion_tiempo_real and todos_activos:
        return "🟢", "Defender y el firewall están activos y protegiendo el equipo.", defender, firewall

    if servicio_activo and not proteccion_tiempo_real:
        return (
            "🟡",
            "Defender puede estar en modo pasivo (habitual si hay otro antivirus de terceros activo).",
            defender,
            firewall,
        )

    if not todos_activos:
        return "🟡", "Al menos un perfil del firewall está desactivado.", defender, firewall

    return "🔴", "La protección en tiempo real de Defender está desactivada.", defender, firewall


def _renderizar_sidebar() -> str:
    """Dibuja la barra lateral (título, semáforo, selector de proveedor) y devuelve el código de proveedor activo."""
    with st.sidebar:
        st.title("🛡️ ProtexiumAI")
        st.caption("Asistente de seguridad conversacional para Windows 11")
        st.markdown("---")

        st.subheader("Estado del sistema")
        actualizar = st.button("🔄 Actualizar estado")
        if st.session_state["estado_defender"] is None or actualizar:
            color, mensaje, defender, firewall = _calcular_semaforo()
            st.session_state["estado_defender"] = defender
            st.session_state["estado_firewall"] = firewall
            st.session_state["semaforo"] = (color, mensaje)
        color, mensaje = st.session_state.get("semaforo", ("🔴", "Sin datos todavía."))
        st.markdown(f"### {color} {mensaje}")

        st.markdown("---")
        st.subheader("Proveedor LLM")
        etiqueta = st.radio(
            "Proveedor",
            options=list(PROVEEDORES.keys()),
            disabled=st.session_state["hilo"] is not None,
            label_visibility="collapsed",
            key="proveedor_radio",
        )
        codigo_proveedor = PROVEEDORES[etiqueta]
        st.caption(NOTA_PRIVACIDAD[codigo_proveedor])

    return codigo_proveedor


def _renderizar_historial() -> None:
    for entrada in st.session_state["historial_ui"]:
        with st.chat_message(entrada["role"]):
            st.markdown(entrada["content"])


def _formatear_error(error: Exception, codigo_proveedor: str) -> str:
    if isinstance(error, AuthenticationError):
        return "**Error:** la API key no es válida. Revisa `GROQ_API_KEY` en tu archivo `.env`."
    if isinstance(error, APIConnectionError):
        if codigo_proveedor == "ollama":
            return (
                "**No se pudo conectar con Ollama.** Comprueba que esté en marcha "
                "(`ollama serve`) y que el modelo esté descargado (`ollama pull llama3.2:3b`)."
            )
        return "**Error:** no se ha podido conectar con el proveedor LLM. Comprueba tu conexión a internet."
    if isinstance(error, APIError):
        return f"**Error al llamar al proveedor LLM:** {error}"
    return f"**Error inesperado:** {error}"


def _formatear_resultado(resultado: ResultadoTurno) -> str:
    lineas = []
    for herramienta in resultado.herramientas:
        if herramienta.ejecutada:
            icono = "✅" if herramienta.ok else "⚠️"
            estado_txt = "ejecutada" if herramienta.ok else "ejecutada con error"
        else:
            icono = "🚫"
            estado_txt = "cancelada"
        lineas.append(f"{icono} *{herramienta.tool_id}* ({herramienta.nivel}) — {estado_txt}: {herramienta.resumen}")
    if lineas:
        lineas.append("")
    lineas.append(resultado.respuesta)
    return "\n".join(lineas)


def _renderizar_propuesta_pendiente(estado: EstadoTurno) -> None:
    propuesta = estado.propuesta
    if propuesta is None:
        return

    spec = executor.WHITELIST.get(propuesta["tool_id"])
    with st.chat_message("assistant"):
        st.markdown(f"**Quiero ejecutar:** {propuesta['descripcion']}")
        if propuesta["params"]:
            st.json(propuesta["params"])
        st.caption(f"Nivel: {ETIQUETA_NIVEL.get(propuesta['nivel'], propuesta['nivel'])}")

        if spec is not None and spec.requiere_admin and not executor._es_administrador():
            st.warning(
                "Esta acción requiere permisos de administrador. Cierra la aplicación y "
                "vuelve a lanzarla desde una terminal PowerShell elevada "
                "(`streamlit run app/streamlit_app.py`) para poder confirmarla."
            )

        col_confirmar, col_cancelar = st.columns(2)
        with col_confirmar:
            if st.button("✅ Confirmar", key=f"confirmar_{id(estado)}_{propuesta['tool_id']}", use_container_width=True):
                estado.decision = True
                estado.evento_decision.set()
                st.rerun()
        with col_cancelar:
            if st.button("❌ Cancelar", key=f"cancelar_{id(estado)}_{propuesta['tool_id']}", use_container_width=True):
                estado.decision = False
                estado.evento_decision.set()
                st.rerun()


def _gestionar_turno_en_curso(codigo_proveedor: str) -> None:
    contenedor_estado = st.session_state["contenedor_estado"]
    estado: EstadoTurno = contenedor_estado["actual"]

    with st.spinner("ProtexiumAI está pensando..."):
        while not estado.terminado and estado.propuesta is None:
            time.sleep(0.1)

    if estado.propuesta is not None:
        _renderizar_propuesta_pendiente(estado)
        return

    # estado.terminado: el turno ha acabado, se procesa y se limpia.
    if estado.error is not None:
        contenido = _formatear_error(estado.error, codigo_proveedor)
    else:
        contenido = _formatear_resultado(estado.resultado)
        hubo_mutacion = any(h.ejecutada and h.ok and h.nivel in ("accion", "mutante") for h in estado.resultado.herramientas)
        if hubo_mutacion:
            color, mensaje, defender, firewall = _calcular_semaforo()
            st.session_state["estado_defender"] = defender
            st.session_state["estado_firewall"] = firewall
            st.session_state["semaforo"] = (color, mensaje)

    st.session_state["historial_ui"].append({"role": "assistant", "content": contenido})
    st.session_state["hilo"] = None
    contenedor_estado["actual"] = None
    st.rerun()


def main() -> None:
    _inicializar_estado()
    codigo_proveedor = _renderizar_sidebar()
    _asegurar_agente(codigo_proveedor)

    _renderizar_historial()

    if st.session_state["hilo"] is not None:
        _gestionar_turno_en_curso(codigo_proveedor)

    mensaje = st.chat_input(
        "Escribe tu pregunta o petición...",
        disabled=st.session_state["hilo"] is not None or st.session_state["agente"] is None,
    )
    if mensaje:
        st.session_state["historial_ui"].append({"role": "user", "content": mensaje})
        estado = EstadoTurno()
        st.session_state["contenedor_estado"]["actual"] = estado
        hilo = threading.Thread(
            target=_ejecutar_turno,
            args=(st.session_state["agente"], mensaje, estado),
            daemon=True,
        )
        st.session_state["hilo"] = hilo
        hilo.start()
        st.rerun()


if __name__ == "__main__":
    main()
