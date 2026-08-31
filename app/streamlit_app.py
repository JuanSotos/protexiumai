"""Interfaz gráfica de ProtexiumAI construida con Streamlit.

Solo vista y orquestación. La redacción vive en app/textos.py, las lecturas del
equipo en app/lecturas.py y la traducción del registro en app/auditoria.py; la
whitelist, los niveles, la confirmación y la auditoría siguen íntegramente en
src/, que este módulo únicamente lee.
"""

from __future__ import annotations

import html
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# `streamlit run` coloca el directorio del propio script (app/) en sys.path,
# no la raíz del repositorio: hay que añadirla a mano para poder importar src.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from openai import APIConnectionError, APIError, AuthenticationError, OpenAI

from app import auditoria, lecturas, textos
from app.cliente_observado import ClienteObservado, Lote
from src import executor
from src.agent import Agent, ResultadoHerramienta, ResultadoTurno
from src.config import PerfilLLM, cargar_perfil

st.set_page_config(
    page_title="ProtexiumAI",
    page_icon="🛡️",
    layout="centered",
    initial_sidebar_state="expanded",
)

PROVEEDORES = {
    "groq": {"nombre": "En la nube · Groq", "nota": "Tus preguntas salen del equipo"},
    "ollama": {"nombre": "En este equipo · Ollama", "nota": "Nada sale de tu ordenador"},
}

# Los cuatro trabajos que no devuelven informe al terminar (§13).
SIN_INFORME = tuple(textos.SIN_DATOS_AL_TERMINAR)

CONTRATO_ENTRADA = "Lectura sin permiso · acciones y cambios, solo con tu clic · todo queda registrado"


@dataclass
class EstadoTurno:
    """Estado compartido entre el hilo trabajador (agente) y el hilo principal (Streamlit)."""

    mensaje: str = ""
    proveedor: str = "groq"
    evento_decision: threading.Event = field(default_factory=threading.Event)
    propuesta: dict[str, Any] | None = None
    decision: bool | None = None
    resultado: ResultadoTurno | None = None
    error: Exception | None = None
    terminado: bool = False
    # Cola de órdenes del lote en curso (§8), herramienta en marcha (§4) y
    # parámetros ya vistos, para poder nombrar en llano cada paso del recibo.
    ordenes: list[str] = field(default_factory=list)
    orden_indice: int = 0
    en_curso: str | None = None
    ejecutando: dict[str, Any] | None = None
    params_vistos: dict[str, dict[str, Any]] = field(default_factory=dict)
    abandonado: bool = False


# ---------------------------------------------------------------------------
# Puentes con el agente (sin tocar su lógica)
# ---------------------------------------------------------------------------

def _confirmar(contenedor_estado: dict[str, Any], tool_id: str, descripcion: str, params: dict[str, Any]) -> bool:
    """Callback de confirmación del Agent: publica la propuesta y bloquea el hilo trabajador.

    Se ejecuta en el hilo en segundo plano. Publica la propuesta en el EstadoTurno
    activo y espera a que el hilo principal marque evento_decision tras el clic.
    """
    estado: EstadoTurno | None = contenedor_estado["actual"]
    if estado is None or estado.abandonado:
        # El turno ya no está en pantalla (el usuario dejó de esperar): no hay
        # nadie a quien preguntar, así que no se autoriza nada.
        return False
    spec = executor.WHITELIST.get(tool_id)
    estado.orden_indice += 1
    estado.en_curso = tool_id
    estado.ejecutando = None
    estado.params_vistos[tool_id] = dict(params)
    estado.propuesta = {
        "tool_id": tool_id,
        "descripcion": descripcion,
        "params": params,
        "nivel": spec.nivel if spec is not None else "desconocido",
        "posicion": estado.orden_indice,
        "total": max(len(estado.ordenes), estado.orden_indice),
    }
    estado.evento_decision.clear()
    estado.evento_decision.wait()
    decision = estado.decision
    estado.propuesta = None
    return bool(decision)


def _observar_lote(contenedor_estado: dict[str, Any], lote: Lote) -> None:
    """Anota qué ha pedido el modelo en este lote: cuántas órdenes y qué corre ahora."""
    estado: EstadoTurno | None = contenedor_estado["actual"]
    if estado is None:
        return
    estado.ordenes = list(lote.ordenes)
    estado.orden_indice = 0
    estado.en_curso = lote.herramientas[0] if lote.herramientas else None
    estado.ejecutando = None


def _ejecutar_turno(agente: Agent, mensaje: str, estado: EstadoTurno) -> None:
    """Función objetivo del hilo trabajador: llama al agente y vuelca el resultado."""
    try:
        estado.resultado = agente.enviar_mensaje(mensaje)
    except Exception as error:  # noqa: BLE001 — se reporta en la UI, no se deja escapar al hilo
        estado.error = error
    finally:
        estado.terminado = True


def _construir_perfil(codigo_proveedor: str) -> PerfilLLM:
    """Construye el PerfilLLM del proveedor elegido reutilizando cargar_perfil()."""
    os.environ["LLM_PROVIDER"] = codigo_proveedor
    return cargar_perfil()


def _asegurar_agente(codigo_proveedor: str) -> None:
    """Crea (o recrea al cambiar de proveedor) la instancia de Agent."""
    if st.session_state["agente"] is not None and st.session_state["proveedor_actual"] == codigo_proveedor:
        return
    contenedor_estado = st.session_state["contenedor_estado"]
    try:
        perfil = _construir_perfil(codigo_proveedor)
        cliente = ClienteObservado(
            OpenAI(base_url=perfil.base_url, api_key=perfil.api_key),
            lambda lote: _observar_lote(contenedor_estado, lote),
        )
        st.session_state["agente"] = Agent(
            perfil=perfil,
            confirmar=lambda tool_id, descripcion, params: _confirmar(contenedor_estado, tool_id, descripcion, params),
            cliente=cliente,
        )
        st.session_state["proveedor_actual"] = codigo_proveedor
    except ValueError as error:
        st.session_state["agente"] = None
        st.error(f"Error de configuración del proveedor LLM: {error}")


# ---------------------------------------------------------------------------
# Estado de sesión
# ---------------------------------------------------------------------------

def _inicializar_estado() -> None:
    st.session_state.setdefault("historial_ui", [])
    st.session_state.setdefault("proveedor_actual", None)
    st.session_state.setdefault("codigo_proveedor_elegido", "groq")
    st.session_state.setdefault("agente", None)
    st.session_state.setdefault("hilo", None)
    st.session_state.setdefault("contenedor_estado", {"actual": None})
    st.session_state.setdefault("estado_defender", None)
    st.session_state.setdefault("estado_firewall", None)
    st.session_state.setdefault("semaforo", None)
    st.session_state.setdefault("sesion", None)
    st.session_state.setdefault("tema", "light")
    st.session_state.setdefault("pantalla", None)
    st.session_state.setdefault("bloques_estado", {})
    st.session_state.setdefault("filtro_auditoria", "todo")
    st.session_state.setdefault("alcance_irreversible", {})
    st.session_state.setdefault("aviso_sidebar", None)
    # Marca de arranque: el registro de auditoría de la pantalla se acota a esta
    # sesión, aunque el archivo conserve todo lo anterior.
    st.session_state.setdefault("inicio_sesion", datetime.now().astimezone())


def _refrescar_estado_equipo() -> None:
    semaforo, defender, firewall = lecturas.calcular_semaforo()
    st.session_state["semaforo"] = semaforo
    st.session_state["estado_defender"] = defender
    st.session_state["estado_firewall"] = firewall


def _empezar_conversacion(aviso: str | None = None) -> None:
    """Vacía la conversación. El registro de auditoría no se toca nunca."""
    st.session_state["historial_ui"] = []
    st.session_state["agente"] = None
    st.session_state["proveedor_actual"] = None
    st.session_state["pantalla"] = None
    st.session_state["aviso_sidebar"] = aviso


# ---------------------------------------------------------------------------
# Helpers de presentación
# ---------------------------------------------------------------------------

def _e(texto: Any) -> str:
    return html.escape(str(texto))


def _microlabel(texto: str, clase: str = "") -> str:
    return f'<div class="pxa-microlabel {clase}">{_e(texto)}</div>'


def _saludo() -> str:
    hora = datetime.now().hour
    if hora < 12:
        return "Buenos días"
    if hora < 20:
        return "Buenas tardes"
    return "Buenas noches"


def _comando_previsto(tool_id: str, params: dict[str, Any]) -> str | None:
    spec = executor.WHITELIST.get(tool_id)
    if spec is None:
        return None
    try:
        return spec.plantilla.format(**params) if spec.parametros else spec.plantilla
    except (KeyError, ValueError):
        return None


def _quien_autorizo(h: ResultadoHerramienta) -> str:
    if h.nivel == "lectura":
        return textos.AUTOR_SIN_PERMISO
    if h.ejecutada:
        return textos.AUTOR_AUTORIZADO
    return textos.AUTOR_RECHAZADO


def _construir_filas(
    herramientas: list[ResultadoHerramienta], params_vistos: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Filas del recibo: nombre en llano, tool_id + nivel en el metadato y quién autorizó."""
    filas = []
    for h in herramientas:
        hecha = bool(h.ejecutada and h.ok)
        filas.append(
            {
                "marca": "✓" if hecha else ("!" if h.ejecutada else "—"),
                "titulo": textos.frase(h.tool_id, params_vistos.get(h.tool_id, {}), "hecho" if hecha else "sin_hacer"),
                "meta": f"{h.tool_id} · {h.nivel}",
                "autor": _quien_autorizo(h),
                "error": bool(h.ejecutada and not h.ok),
            }
        )
    return filas


def _titular_y_resto(prosa: str) -> tuple[str, str]:
    """Parte la respuesta en titular (primera frase) y párrafo, como pide el §6 del README."""
    texto = textos.limpiar_respuesta(prosa or "").strip()
    if not texto:
        return "", ""
    for corte in (". ", ".\n", "? ", "! "):
        indice = texto.find(corte)
        if 0 < indice <= 120:
            return texto[: indice + 1].strip(), texto[indice + len(corte) :].strip()
    if len(texto) <= 120:
        return texto, ""
    return "", texto


def _cargar_css() -> str:
    return (Path(__file__).parent / "estilos.css").read_text(encoding="utf-8")


def _inyectar_estilos() -> None:
    st.markdown(f"<style>{_cargar_css()}</style>", unsafe_allow_html=True)
    if st.session_state.get("tema") == "dark":
        # Streamlit no ejecuta <script> insertado vía unsafe_allow_html; en su lugar
        # se pinta un marcador invisible que estilos.css detecta con :has() desde stApp.
        st.markdown('<span class="pxa-theme-dark-marker"></span>', unsafe_allow_html=True)


def _html_semaforo(semaforo: lecturas.Semaforo) -> str:
    """Semáforo con las ondas del ADDENDUM-01 y las variantes de vocabulario del §10."""
    clases = ["pxa-onda-contenedor"]
    if not semaforo.ondas:
        clases.append("pxa-sin-ondas")
    estatico = "pxa-ring-static pxa-discontinuo" if semaforo.discontinuo else "pxa-ring-static"
    return (
        f'<div class="{" ".join(clases)}">'
        f'<div class="pxa-onda-ring"></div><div class="pxa-onda-ring"></div><div class="pxa-onda-ring"></div>'
        f'<div class="{estatico}"></div>'
        f'<div class="pxa-ring-inner"><div class="pxa-dot-centro"></div></div>'
        f"</div>"
    )


# ---------------------------------------------------------------------------
# Barra lateral
# ---------------------------------------------------------------------------

def _html_filas_resumen() -> str:
    filas = lecturas.filas_resumen(st.session_state.get("estado_defender"), st.session_state.get("estado_firewall"))
    cuerpo = "".join(
        f'<div class="pxa-checks-row pxa-{estilo}"><span>{_e(etiqueta)}</span><span>{_e(valor)}</span></div>'
        for estilo, etiqueta, valor in filas
    )
    return f'<div class="pxa-checks">{cuerpo}</div>'


def _sidebar_estado() -> None:
    hora = datetime.now().strftime("%H:%M")
    st.markdown(
        f'<div class="pxa-sidebar-row"><span class="pxa-microlabel">Estado del equipo</span>'
        f'<span class="pxa-tabular pxa-hora">{hora}</span></div>',
        unsafe_allow_html=True,
    )

    semaforo: lecturas.Semaforo = st.session_state["semaforo"]
    st.markdown(
        f'<div class="pxa-semaforo" style="--e:{semaforo.color}">'
        f"{_html_semaforo(semaforo)}"
        f'<div class="pxa-semaforo-texto"><h3>{_e(semaforo.titular)}</h3><p>{_e(semaforo.nota)}</p></div>'
        f"</div>",
        unsafe_allow_html=True,
    )
    st.markdown(_html_filas_resumen(), unsafe_allow_html=True)

    col_comprobar, col_detalle = st.columns(2)
    with col_comprobar:
        if st.button("Volver a comprobar", key="pxa_actualizar", use_container_width=True):
            _refrescar_estado_equipo()
            st.rerun()
    with col_detalle:
        if st.button("Ver el detalle", key="pxa_ver_detalle", use_container_width=True):
            st.session_state["pantalla"] = "detalle"
            st.rerun()


def _sidebar_sesion() -> None:
    """§9 · Con qué cuenta se ha entrado y qué queda fuera de alcance por ello."""
    sesion: lecturas.Sesion = st.session_state["sesion"]
    if sesion.es_admin:
        st.markdown(
            f'<div class="pxa-sesion"><div class="pxa-sidebar-row">'
            f'<span class="pxa-microlabel">Esta sesión</span>'
            f'<span class="pxa-sesion-valor">Con administrador</span></div>'
            f'<p class="pxa-sesion-texto">{_e(textos.SESION_CON_ADMIN)}</p></div>',
            unsafe_allow_html=True,
        )
        return
    st.markdown(
        f'<div class="pxa-sesion"><div class="pxa-sidebar-row">'
        f'<span class="pxa-microlabel">Esta sesión</span>'
        f'<span class="pxa-sesion-valor pxa-warn">Sin administrador</span></div>'
        f'<p class="pxa-sesion-texto">{_e(sesion.resumen)}</p></div>',
        unsafe_allow_html=True,
    )
    with st.expander("Qué significa"):
        st.markdown(textos.SESION_QUE_SIGNIFICA)


def _sidebar_cola(estado: EstadoTurno | None) -> None:
    """§8 · Tarjeta de cola mientras hay una propuesta esperando decisión."""
    if estado is None or estado.propuesta is None:
        return
    total = int(estado.propuesta.get("total", 1))
    posicion = int(estado.propuesta.get("posicion", 1))
    if total > 1:
        restantes = total - posicion
        cola = "la otra espera su turno" if restantes == 1 else f"las otras {restantes} esperan su turno"
        texto = f"Orden {posicion} de {total} · {cola}" if restantes > 0 else f"Orden {posicion} de {total} · es la última"
    else:
        texto = "Una orden esperando · nada ocurre hasta que decidas"
    st.markdown(
        f'<div class="pxa-cola">{_microlabel("Esperando tu decisión", "pxa-label-gold")}'
        f'<div class="pxa-cola-texto">{_e(texto)}</div></div>',
        unsafe_allow_html=True,
    )


def _sidebar_proveedor(hay_turno: bool) -> str:
    st.markdown(_microlabel("Dónde se procesa"), unsafe_allow_html=True)
    codigo_elegido = st.session_state["codigo_proveedor_elegido"]
    for codigo, info in PROVEEDORES.items():
        activo = codigo == codigo_elegido
        with st.container(key=f"pxa_prov_{codigo}_{'on' if activo else 'off'}"):
            # La clave del botón no comparte prefijo con la de la tarjeta: si lo
            # compartiera, el selector [class*="st-key-pxa_prov_"] pintaría también
            # su contenedor y se vería una caja dentro de otra.
            if st.button(info["nombre"], key=f"pxa_provbtn_{codigo}", use_container_width=True, disabled=hay_turno):
                if codigo != codigo_elegido:
                    st.session_state["codigo_proveedor_elegido"] = codigo
                    _empezar_conversacion(textos.AVISO_CAMBIO_PROVEEDOR)
                st.rerun()
            st.caption(info["nota"])
    st.markdown(f'<p class="pxa-nota-proveedor">{_e(textos.AVISO_CAMBIO_PROVEEDOR)}</p>', unsafe_allow_html=True)
    return codigo_elegido


def _sidebar_pie() -> None:
    with st.container(key="pxa_pie_sidebar"):
        if st.button("Empezar una conversación nueva", key="pxa_nueva", use_container_width=True):
            _empezar_conversacion(textos.AVISO_CONVERSACION_NUEVA)
            st.rerun()

        aviso = st.session_state.get("aviso_sidebar")
        if aviso:
            st.markdown(f'<p class="pxa-aviso">{_e(aviso)}</p>', unsafe_allow_html=True)

        # Rótulo a la izquierda y el conmutador a la derecha, en una sola fila: el
        # CSS junta las dos columnas de botones en una única pastilla segmentada.
        tema_actual = st.session_state["tema"]
        col_rotulo, col_claro, col_oscuro = st.columns([1.05, 0.55, 0.65])
        with col_rotulo:
            st.markdown(_microlabel("Apariencia"), unsafe_allow_html=True)
        with col_claro:
            if st.button("Claro", key=f"pxa_tema_light_{'on' if tema_actual == 'light' else 'off'}", use_container_width=True):
                st.session_state["tema"] = "light"
                st.rerun()
        with col_oscuro:
            if st.button("Oscuro", key=f"pxa_tema_dark_{'on' if tema_actual == 'dark' else 'off'}", use_container_width=True):
                st.session_state["tema"] = "dark"
                st.rerun()
        st.markdown(
            '<p class="pxa-contrato">Nunca cambio un ajuste de tu equipo sin tu permiso.</p>',
            unsafe_allow_html=True,
        )


def _renderizar_sidebar(estado: EstadoTurno | None) -> str:
    """Dibuja la barra lateral completa y devuelve el proveedor activo."""
    with st.sidebar:
        st.markdown(
            '<div class="pxa-brand"><div class="pxa-brand-mark"><span></span></div>'
            '<div class="pxa-brand-name">Protexium<em>AI</em></div></div>'
            '<p class="pxa-brand-sub">Asistente de seguridad para Windows 11</p>',
            unsafe_allow_html=True,
        )

        with st.container(key="pxa_zona_scroll"):
            _sidebar_estado()
            _sidebar_sesion()
            _sidebar_cola(estado)
            codigo_elegido = _sidebar_proveedor(hay_turno=st.session_state["hilo"] is not None)

        _sidebar_pie()
    return codigo_elegido


# ---------------------------------------------------------------------------
# Cabecera y fila fina de estado (barra lateral plegada, §14)
# ---------------------------------------------------------------------------

def _renderizar_cabecera() -> None:
    st.markdown(
        f'<div class="pxa-cabecera"><span class="pxa-microlabel">Sesión</span>'
        f'<span class="pxa-cabecera-fecha pxa-tabular">{lecturas.fecha_romana(datetime.now())}</span></div>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Bienvenida
# ---------------------------------------------------------------------------

def _renderizar_bienvenida() -> str | None:
    st.markdown(
        f'<div class="pxa-bienvenida"><div class="pxa-filete"></div>'
        f"<h1>{_e(_saludo())}</h1>"
        f'<p class="pxa-intro">Pregúntame por tu equipo con tus propias palabras. '
        f"Yo lo reviso y te lo explico sin tecnicismos.</p>"
        f'<div class="pxa-filete"></div>'
        f'<div class="pxa-microlabel">Para empezar</div></div>',
        unsafe_allow_html=True,
    )
    seleccion = None
    with st.container(key="pxa_sugerencias"):
        for i, texto in enumerate(textos.SUGERENCIAS):
            if st.button(texto, key=f"pxa_sug_{i}", use_container_width=True):
                seleccion = texto
        if st.button("Ver todo lo que puedo mirar", key="pxa_ir_catalogo"):
            st.session_state["pantalla"] = "catalogo"
            st.rerun()
    return seleccion


# ---------------------------------------------------------------------------
# Conversación
# ---------------------------------------------------------------------------

def _renderizar_burbuja_usuario(texto: str, indice: int) -> None:
    """Mensaje del usuario: bloque propio alineado a la derecha (README §4).

    Se pinta como HTML de una pieza y no con un contenedor de Streamlit porque
    ese contenedor imponía su propio ancho y partía la frase. El texto se escapa
    ANTES de convertir los saltos, para que un mensaje no pueda inyectar marcado.
    """
    cuerpo = _e(texto).replace("\n", "<br>")
    st.markdown(
        f'<div class="pxa-msg-usuario"><span class="pxa-microlabel">Tú</span>'
        f'<div class="pxa-burbuja">{cuerpo}</div></div>',
        unsafe_allow_html=True,
    )


def _rotulo_protexium(proveedor: str | None) -> str:
    marca = textos.PROVEEDOR_TURNO.get(str(proveedor), "")
    sufijo = f'<span class="pxa-microlabel pxa-proveedor">{_e(marca)}</span>' if marca else ""
    return f'<div class="pxa-firma"><span class="pxa-microlabel pxa-label-gold">Protexium</span>{sufijo}</div>'


def _renderizar_prosa_asistente(entrada: dict[str, Any], key: str) -> None:
    with st.container(key=key):
        st.markdown(_rotulo_protexium(entrada.get("proveedor")), unsafe_allow_html=True)
        titular = entrada.get("titular")
        if titular:
            st.markdown(f'<h2 class="pxa-titular">{_e(titular)}</h2>', unsafe_allow_html=True)
        cuerpo = textos.limpiar_respuesta(entrada.get("content") or "")
        if cuerpo:
            st.markdown(cuerpo)
        elif not titular:
            st.markdown("_(sin respuesta)_")


def _renderizar_siguiente_paso(entrada: dict[str, Any], indice: int) -> str | None:
    """§13 · Un solo botón de acento con el siguiente paso en llano."""
    tool_id = entrada.get("sin_datos")
    if not tool_id:
        return None
    copia = textos.SIN_DATOS_AL_TERMINAR[tool_id]
    with st.container(key=f"pxa_paso_{indice}"):
        if st.button(copia["boton"], key=f"pxa_btn_paso_{indice}"):
            return copia["pregunta"]
    return None


def _renderizar_recibo(entrada: dict[str, Any], indice: int) -> None:
    filas = entrada["filas"]
    with st.container(key=f"pxa_recibo_{indice}"):
        n = len(filas)
        st.markdown(
            f'<div class="pxa-recibo-cabecera"><span class="pxa-microlabel">Qué he hecho</span>'
            f'<span class="pxa-tabular">{n} paso{"s" if n != 1 else ""} · {_e(entrada.get("hora", ""))}</span></div>',
            unsafe_allow_html=True,
        )
        for fila in filas:
            clase_error = "pxa-error" if fila.get("error") else ""
            st.markdown(
                f'<div class="pxa-recibo-fila {clase_error}">'
                f'<span class="pxa-recibo-marca">{fila["marca"]}</span>'
                f'<div class="pxa-recibo-cuerpo">'
                f'<div class="pxa-recibo-titulo">{_e(fila["titulo"])}</div>'
                f'<div class="pxa-recibo-meta pxa-tabular">{_e(fila["meta"])}</div>'
                f"</div>"
                f'<span class="pxa-recibo-autor">{_e(fila["autor"])}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )
        if st.button("Ver el registro de auditoría", key=f"pxa_ir_auditoria_{indice}"):
            st.session_state["pantalla"] = "auditoria"
            st.rerun()


def _renderizar_tarjeta_error(entrada: dict[str, Any], indice: int) -> None:
    """Fallo del proveedor de IA: la tarjeta "Sin conexión" del README §7."""
    with st.container(key=f"pxa_offline_{indice}"):
        st.markdown(
            f'<span class="pxa-microlabel">No he podido conectar</span>'
            f'<h2>{_e(entrada["titular"])}</h2>'
            f'<div class="pxa-filete pxa-filete-ancho"></div>',
            unsafe_allow_html=True,
        )
        st.markdown(textos.TRANQUILIDAD_PROVEEDOR)
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Reintentar", key=f"pxa_btn_reintentar_{indice}", use_container_width=True):
                st.session_state["reintentar_mensaje"] = entrada.get("mensaje_original", "")
                st.rerun()
        with col_b:
            if st.button("Usar el modo local", key=f"pxa_btn_modolocal_{indice}", use_container_width=True):
                st.session_state["codigo_proveedor_elegido"] = "ollama"
                _empezar_conversacion(textos.AVISO_CAMBIO_PROVEEDOR)
                st.rerun()
        with st.expander("Detalle técnico del error"):
            st.markdown(entrada["detalle"])


def _renderizar_tarjeta_fallo(entrada: dict[str, Any], indice: int) -> str | None:
    """§5 · Molde común de los errores del sistema: primero la tranquilidad."""
    caso = entrada.get("caso", "error_powershell")
    titular, segunda = textos.ERRORES_SISTEMA.get(caso, textos.ERRORES_SISTEMA["error_powershell"])
    reintento = None
    with st.container(key=f"pxa_fallo_{indice}"):
        st.markdown(
            f'<span class="pxa-microlabel">{_e(textos.ROTULO_FALLO)}</span>'
            f"<h2>{_e(titular)}</h2>"
            f'<div class="pxa-filete pxa-filete-ancho"></div>'
            f'<p class="pxa-fallo-texto">{_e(textos.TRANQUILIDAD_SISTEMA)} {_e(segunda)}</p>',
            unsafe_allow_html=True,
        )
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Inténtalo otra vez", key=f"pxa_btn_fallo_reintentar_{indice}", use_container_width=True):
                reintento = entrada.get("mensaje_original", "")
        with col_b:
            st.button("Déjalo", key=f"pxa_btn_fallo_dejalo_{indice}", use_container_width=True)
        with st.expander("Ver el detalle técnico"):
            for etiqueta, valor in entrada.get("detalle", []):
                st.markdown(
                    f'<div class="pxa-detalle-row"><span class="pxa-detalle-label">{_e(etiqueta)}</span>'
                    f'<span class="pxa-detalle-valor pxa-tabular">{_e(valor)}</span></div>',
                    unsafe_allow_html=True,
                )
    return reintento or None


def _renderizar_tiempo_agotado(entrada: dict[str, Any], indice: int) -> str | None:
    """§4 · Desenlace por tiempo agotado. No es un error: ni color crítico ni culpa."""
    mensaje = None
    with st.container(key=f"pxa_agotado_{indice}"):
        st.markdown(
            f'<span class="pxa-microlabel">Sigue en marcha</span>'
            f"<h2>{_e(textos.TIEMPO_AGOTADO_TITULAR)}</h2>"
            f'<p class="pxa-fallo-texto">{_e(textos.TIEMPO_AGOTADO_TEXTO)}</p>',
            unsafe_allow_html=True,
        )
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("Mira cómo va", key=f"pxa_btn_comova_{indice}", use_container_width=True):
                mensaje = "¿Cómo ha quedado el análisis? Mira el estado de Defender y las amenazas detectadas."
        with col_b:
            st.button("Déjalo por ahora", key=f"pxa_btn_dejalo_{indice}", use_container_width=True)
    return mensaje


def _renderizar_entrada_historial(entrada: dict[str, Any], indice: int) -> str | None:
    """Pinta una entrada del historial y devuelve el mensaje que haya pedido el usuario."""
    if entrada["role"] == "user":
        _renderizar_burbuja_usuario(entrada["content"], indice)
        return None

    kind = entrada.get("kind", "conversacion")
    if kind == "error":
        _renderizar_tarjeta_error(entrada, indice)
        return None
    if kind == "fallo":
        return _renderizar_tarjeta_fallo(entrada, indice)
    if kind == "tiempo_agotado":
        return _renderizar_tiempo_agotado(entrada, indice)

    _renderizar_prosa_asistente(entrada, key=f"pxa_asis_{indice}")
    mensaje = _renderizar_siguiente_paso(entrada, indice)

    if kind == "receta":
        _renderizar_recibo(entrada, indice)
        return mensaje

    lecturas_hechas = entrada.get("lecturas") or []
    if lecturas_hechas:
        etiqueta = f"Qué he consultado · {len(lecturas_hechas)} lectura{'s' if len(lecturas_hechas) != 1 else ''}"
        with st.expander(etiqueta):
            for l in lecturas_hechas:
                st.markdown(f"- **{l['titulo']}** — {l['resumen']}")
    return mensaje


# ---------------------------------------------------------------------------
# Propuesta pendiente de confirmación
# ---------------------------------------------------------------------------

def _alcance_irreversible(tool_id: str) -> tuple[str | None, list[str]]:
    """Lee (una sola vez) qué se va a borrar o qué reglas se pierden, sin tocar nada."""
    cache: dict[str, Any] = st.session_state["alcance_irreversible"]
    if tool_id in cache:
        return cache[tool_id]["resumen"], cache[tool_id]["elementos"]

    resumen: str | None = None
    elementos: list[str] = []
    if tool_id == "remove_all_threats":
        resultado = executor.execute("get_detected_threats", {}, proveedor=None)
        if resultado["ok"]:
            detecciones = resultado["data"] or []
            for deteccion in detecciones:
                if not isinstance(deteccion, dict):
                    continue
                recursos = deteccion.get("Resources") or []
                ruta = str(recursos[0]) if recursos else f"Amenaza {deteccion.get('ThreatID', '?')}"
                elementos.append(ruta.replace("file:_", ""))
            resumen = f"{len(elementos)} archivos en cuarentena" if elementos else "No hay nada en cuarentena ahora mismo"
    elif tool_id == "restore_firewall_defaults":
        resultado = executor.execute("get_allowed_firewall_rules", {}, proveedor=None)
        if resultado["ok"]:
            reglas = resultado["data"] or []
            elementos = [str(r.get("DisplayName", "regla sin nombre")) for r in reglas if isinstance(r, dict)]
            resumen = f"hay {len(elementos)} reglas de entrada activas ahora mismo"

    cache[tool_id] = {"resumen": resumen, "elementos": elementos}
    return resumen, elementos


def _renderizar_detalle_tecnico(tool_id: str, params: dict[str, Any], nivel: str, irreversible: bool) -> None:
    spec = executor.WHITELIST.get(tool_id)
    comando = _comando_previsto(tool_id, params) or "—"
    nivel_txt = nivel
    if irreversible:
        nivel_txt += " · irreversible"
    if spec is not None and spec.requiere_admin:
        nivel_txt += " · requiere administrador"
    filas = [
        ("Herramienta", tool_id),
        ("Nivel", nivel_txt),
        ("Parámetros", " · ".join(f"{k} = {v}" for k, v in params.items()) or "ninguno"),
        ("Comando", comando),
        ("Auditoría", "se registra antes de ejecutarse"),
    ]
    st.markdown(
        "".join(
            f'<div class="pxa-detalle-row"><span class="pxa-detalle-label">{_e(k)}</span>'
            f'<span class="pxa-detalle-valor pxa-tabular">{_e(v)}</span></div>'
            for k, v in filas
        ),
        unsafe_allow_html=True,
    )


def _renderizar_propuesta_pendiente(estado: EstadoTurno) -> None:
    propuesta = estado.propuesta
    if propuesta is None:
        return

    tool_id = propuesta["tool_id"]
    params = propuesta["params"]
    nivel = propuesta["nivel"]
    spec = executor.WHITELIST.get(tool_id)
    irreversible = tool_id in textos.IRREVERSIBLES

    consigue, deshace = textos.consigue_y_deshace(tool_id, params)
    resumen_alcance, elementos = _alcance_irreversible(tool_id) if irreversible else (None, [])
    alcance = textos.alcance(tool_id, params, resumen_alcance)
    etiqueta_nivel = textos.NIVEL_PLANO.get(tool_id, nivel)
    rotulo = textos.ROTULO_PERMISO_IRREVERSIBLE if irreversible else textos.ROTULO_PERMISO
    titular = textos.titular_propuesta(tool_id, params, propuesta["descripcion"])
    total, posicion = int(propuesta.get("total", 1)), int(propuesta.get("posicion", 1))

    clave = f"pxa_permiso_irr_{id(estado)}" if irreversible else f"pxa_permiso_{id(estado)}"
    with st.container(key=clave):
        etiquetas = f'<span class="pxa-nivel-pill">{_e(etiqueta_nivel)}</span>'
        if irreversible:
            etiquetas += f'<span class="pxa-nivel-pill pxa-pill-bad">{_e(textos.ETIQUETA_SIN_VUELTA)}</span>'
        st.markdown(
            f'<div class="pxa-permiso-cabecera"><span class="pxa-microlabel">{_e(rotulo)}</span>'
            f'<span class="pxa-pills">{etiquetas}</span></div>'
            f'<div class="pxa-permiso-cuerpo">'
            + (f'<div class="pxa-permiso-orden">Orden {posicion} de {total}</div>' if total > 1 else "")
            + f'<div class="pxa-permiso-titular">{_e(titular)}</div>'
            f'<div class="pxa-def-row"><div class="pxa-def-label">Sobre qué</div><div>{_e(alcance)}</div></div>'
            f'<div class="pxa-def-row"><div class="pxa-def-label">Qué consigues</div><div>{_e(consigue)}</div></div>'
            f'<div class="pxa-def-row pxa-def-ultima"><div class="pxa-def-label">Se deshace</div>'
            f'<div class="{"pxa-texto-bad" if irreversible else ""}">{_e(deshace)}</div></div>'
            f"</div>",
            unsafe_allow_html=True,
        )

        with st.expander("Ver el detalle técnico"):
            _renderizar_detalle_tecnico(tool_id, params, nivel, irreversible)

        if irreversible:
            etiqueta_lista = textos.ENLACE_ALCANCE[tool_id]
            with st.expander(f"{etiqueta_lista} · {len(elementos)}"):
                if elementos:
                    for elemento in elementos[:40]:
                        st.markdown(f'<div class="pxa-lista-alcance">{_e(elemento)}</div>', unsafe_allow_html=True)
                    if len(elementos) > 40:
                        st.caption(f"y {len(elementos) - 40} más.")
                else:
                    st.caption("No he podido leer la lista; el detalle técnico dice por qué.")
            st.markdown(
                f'<div class="pxa-nota-irreversible">{_e(textos.NOTA_IRREVERSIBLE[tool_id])}</div>',
                unsafe_allow_html=True,
            )

        requiere_admin_sin_permiso = spec is not None and spec.requiere_admin and not executor._es_administrador()

        col_confirmar, col_cancelar, col_nota = st.columns([1.3, 1, 1.7])
        with col_confirmar:
            etiqueta_si = textos.BOTON_SI.get(tool_id, textos.BOTON_SI_POR_DEFECTO)
            clave_si = f"pxa_btn_confirmar{'_bad' if irreversible else ''}_{id(estado)}_{tool_id}"
            if st.button(etiqueta_si, key=clave_si, use_container_width=True, disabled=requiere_admin_sin_permiso):
                estado.ejecutando = {
                    "tool_id": tool_id,
                    "params": dict(params),
                    "desde": time.monotonic(),
                    "hora": datetime.now().strftime("%H:%M"),
                }
                estado.decision = True
                estado.evento_decision.set()
                st.rerun()
        with col_cancelar:
            if st.button("No, déjalo", key=f"pxa_btn_cancelar_{id(estado)}_{tool_id}", use_container_width=True):
                estado.decision = False
                estado.evento_decision.set()
                st.rerun()
        with col_nota:
            st.markdown('<p class="pxa-permiso-nota">Nada ocurre hasta que pulses.</p>', unsafe_allow_html=True)

        if requiere_admin_sin_permiso:
            st.markdown(
                f'<div class="pxa-admin-aviso">'
                f'<span class="pxa-microlabel pxa-warn">Necesita administrador</span>'
                f"<span>{_e(textos.AVISO_ADMIN_PERMISO)}</span></div>",
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Turno en curso: indicador, bloque "ejecutando" y cierre del turno
# ---------------------------------------------------------------------------

def _texto_indicador(estado: EstadoTurno) -> str:
    """§4 · Plantilla del indicador: nombra la herramienta en curso."""
    if estado.en_curso:
        return f"{textos.frase(estado.en_curso, estado.params_vistos.get(estado.en_curso, {}), 'en_curso')} · {textos.COLETILLA_LECTURA}"
    return f"Estoy revisando el sistema · {textos.COLETILLA_LECTURA}"


def _renderizar_pensando(estado: EstadoTurno) -> None:
    st.markdown(
        '<div class="pxa-pensando"><div class="pxa-dots">'
        '<span class="pxa-dot"></span><span class="pxa-dot"></span><span class="pxa-dot"></span>'
        f'</div><span class="pxa-pensando-texto">{_e(_texto_indicador(estado))}</span></div>',
        unsafe_allow_html=True,
    )


def _renderizar_ejecutando(estado: EstadoTurno) -> tuple[Any, bool]:
    """Tarjeta "ejecutando" del §4. Devuelve el hueco del reloj y si hay que dejar de esperar."""
    ejecucion = estado.ejecutando or {}
    tool_id = str(ejecucion.get("tool_id", ""))
    params = ejecucion.get("params", {})
    expectativa = textos.EXPECTATIVA_EJECUCION.get(tool_id, textos.EXPECTATIVA_POR_DEFECTO)

    with st.container(key="pxa_ejecutando"):
        st.markdown(
            '<div class="pxa-ejec-cabecera"><div class="pxa-dots">'
            '<span class="pxa-dot"></span><span class="pxa-dot"></span><span class="pxa-dot"></span>'
            '</div><span class="pxa-microlabel pxa-label-gold">Trabajando en tu equipo</span></div>',
            unsafe_allow_html=True,
        )
        reloj = st.empty()
        st.markdown(
            f'<h2 class="pxa-titular">{_e(textos.frase(tool_id, params, "en_curso"))}</h2>'
            f'<div class="pxa-filete pxa-filete-ancho"></div>'
            f'<p class="pxa-ejec-expectativa">{_e(expectativa)}</p>'
            f'<p class="pxa-ejec-autorizacion">Lo autorizaste tú a las '
            f'<span class="pxa-tabular">{_e(ejecucion.get("hora", ""))}</span>. '
            f"Windows no me deja cancelarlo una vez empezado, pero puedo dejar de esperar.</p>",
            unsafe_allow_html=True,
        )
        dejar = st.button("Dejo de esperar", key="pxa_btn_dejar_esperar")
        with st.expander("Ver el detalle técnico"):
            spec = executor.WHITELIST.get(tool_id)
            nivel = spec.nivel if spec is not None else "desconocido"
            _renderizar_detalle_tecnico(tool_id, params, nivel, tool_id in textos.IRREVERSIBLES)
    return reloj, dejar


def _detalle_tecnico_error(herramienta: ResultadoHerramienta | None, error: Exception | None) -> list[tuple[str, str]]:
    detalle: list[tuple[str, str]] = []
    if herramienta is not None:
        detalle.append(("Herramienta", herramienta.tool_id))
        detalle.append(("Nivel", herramienta.nivel))
        detalle.append(("Salida", herramienta.resumen))
    if error is not None:
        detalle.append(("Excepción", f"{type(error).__name__}: {error}"))
    return detalle or [("Detalle", "sin información adicional")]


def _entrada_de_resultado(resultado: ResultadoTurno, estado: EstadoTurno, hora: str) -> dict[str, Any]:
    """Traduce el ResultadoTurno del agente a la entrada de historial que toca."""
    herramientas = resultado.herramientas
    fallidas = [h for h in herramientas if h.ejecutada and not h.ok]

    # Un análisis que se pasó del plazo del executor no es un fallo (§4).
    agotadas = [h for h in fallidas if auditoria.es_tiempo_agotado(h.resumen)]
    if agotadas:
        return {"role": "assistant", "kind": "tiempo_agotado", "tool_id": agotadas[0].tool_id, "proveedor": estado.proveedor}

    prosa = (resultado.respuesta or "").strip()
    if prosa == textos.RESPUESTA_SIN_CONVERGENCIA:
        return {
            "role": "assistant",
            "kind": "fallo",
            "caso": "sin_convergencia",
            "detalle": [("Herramientas del turno", ", ".join(h.tool_id for h in herramientas) or "ninguna"),
                        ("Límite", "el agente para tras varios intentos sin llegar a una respuesta")],
            "mensaje_original": estado.mensaje,
            "proveedor": estado.proveedor,
        }
    if not prosa and fallidas:
        caso = auditoria.clasificar_error(fallidas[0].resumen) or "error_powershell"
        return {
            "role": "assistant",
            "kind": "fallo",
            "caso": caso,
            "detalle": _detalle_tecnico_error(fallidas[0], None),
            "mensaje_original": estado.mensaje,
            "proveedor": estado.proveedor,
        }

    hay_orden = any(h.nivel in ("accion", "mutante") for h in herramientas)
    sin_datos = next((h.tool_id for h in herramientas if h.ejecutada and h.ok and h.tool_id in SIN_INFORME), None)

    if hay_orden:
        titular, cuerpo = _titular_y_resto(prosa)
        if sin_datos:
            copia = textos.SIN_DATOS_AL_TERMINAR[sin_datos]
            titular = copia["titular"]
            cuerpo = prosa or copia["parrafo"]
        return {
            "role": "assistant",
            "kind": "receta",
            "titular": titular,
            "content": cuerpo,
            "filas": _construir_filas(herramientas, estado.params_vistos),
            "hora": hora,
            "sin_datos": sin_datos,
            "proveedor": estado.proveedor,
        }

    return {
        "role": "assistant",
        "kind": "conversacion",
        "content": prosa,
        "lecturas": [
            {"titulo": textos.frase(h.tool_id, estado.params_vistos.get(h.tool_id, {}), "hecho" if h.ok else "sin_hacer"),
             "resumen": h.resumen}
            for h in herramientas
        ],
        "proveedor": estado.proveedor,
    }


def _cerrar_turno(entrada: dict[str, Any], recalcular: bool) -> None:
    st.session_state["historial_ui"].append(entrada)
    st.session_state["hilo"] = None
    st.session_state["contenedor_estado"]["actual"] = None
    st.session_state["alcance_irreversible"] = {}
    if recalcular:
        _refrescar_estado_equipo()
        st.session_state["bloques_estado"] = {}
    st.rerun()


def _gestionar_turno_en_curso(codigo_proveedor: str) -> None:
    contenedor_estado = st.session_state["contenedor_estado"]
    estado: EstadoTurno = contenedor_estado["actual"]

    if estado.propuesta is not None:
        _renderizar_propuesta_pendiente(estado)
        return

    if not estado.terminado:
        mostrando_ejecucion = estado.ejecutando is not None
        if mostrando_ejecucion:
            reloj, dejar = _renderizar_ejecutando(estado)
            if dejar:
                # No se cancela nada en el equipo: solo se deja de esperar (§4). El
                # agente en curso se descarta para que el siguiente turno empiece limpio.
                estado.abandonado = True
                st.session_state["agente"] = None
                st.session_state["proveedor_actual"] = None
                _cerrar_turno(
                    {"role": "assistant", "kind": "tiempo_agotado", "tool_id": estado.ejecutando.get("tool_id"),
                     "proveedor": estado.proveedor},
                    recalcular=False,
                )
                return
            desde = float((estado.ejecutando or {}).get("desde", time.monotonic()))
        else:
            hueco = st.empty()
            reloj, desde = None, 0.0

        while not estado.terminado and estado.propuesta is None:
            if mostrando_ejecucion:
                if estado.ejecutando is None:
                    st.rerun()
                transcurrido = int(time.monotonic() - desde)
                reloj.markdown(
                    f'<div class="pxa-reloj pxa-tabular">{transcurrido // 60:02d}:{transcurrido % 60:02d} transcurridos</div>',
                    unsafe_allow_html=True,
                )
            else:
                with hueco.container():
                    _renderizar_pensando(estado)
            time.sleep(0.4)
        st.rerun()

    hora = datetime.now().strftime("%H:%M")
    if estado.error is not None:
        info = _formatear_error(estado.error, codigo_proveedor)
        _cerrar_turno(
            {
                "role": "assistant",
                "kind": "error",
                "titular": info["titular"],
                "detalle": info["detalle"],
                "mensaje_original": estado.mensaje,
                "proveedor": estado.proveedor,
            },
            recalcular=False,
        )
        return

    resultado = estado.resultado
    entrada = _entrada_de_resultado(resultado, estado, hora)
    hubo_mutacion = any(h.ejecutada and h.ok and h.nivel in ("accion", "mutante") for h in resultado.herramientas)
    _cerrar_turno(entrada, recalcular=hubo_mutacion)


def _formatear_error(error: Exception, codigo_proveedor: str) -> dict[str, str]:
    """Titular + detalle técnico de un fallo del proveedor de IA (README §7)."""
    if isinstance(error, AuthenticationError):
        return {
            "titular": "Falta la clave de acceso a Groq",
            "detalle": "La API key no es válida. Revisa GROQ_API_KEY en tu archivo .env.",
        }
    if isinstance(error, APIConnectionError):
        if codigo_proveedor == "ollama":
            return {
                "titular": "No consigo hablar con Ollama ahora mismo",
                "detalle": "Comprueba que esté en marcha (ollama serve) y que el modelo esté descargado (ollama pull llama3.2:3b).",
            }
        return {
            "titular": "No consigo hablar con Groq ahora mismo",
            "detalle": "No se ha podido conectar con el proveedor en la nube. Comprueba tu conexión a internet.",
        }
    if isinstance(error, APIError):
        return {"titular": "El proveedor LLM ha devuelto un error", "detalle": str(error)}
    return {"titular": "Ha ocurrido un error inesperado", "detalle": str(error)}


# ---------------------------------------------------------------------------
# Pantallas con acceso explícito
# ---------------------------------------------------------------------------

def _cabecera_pantalla(titulo: str, subtitulo: str, clave: str) -> None:
    if st.button("← Volver a la conversación", key=f"pxa_volver_{clave}"):
        st.session_state["pantalla"] = None
        st.rerun()
    st.markdown(
        f'<div class="pxa-pantalla-cabecera"><h2>{_e(titulo)}</h2>'
        f'<p class="pxa-pantalla-sub">{subtitulo}</p></div>',
        unsafe_allow_html=True,
    )


def _pantalla_estado_detalle() -> None:
    hora = datetime.now().strftime("%H:%M")
    _cabecera_pantalla(
        "Estado del equipo en detalle",
        f'Todo lo que puedo mirar sin cambiar nada. Consultado a las <span class="pxa-tabular">{hora}</span>.',
        "detalle",
    )
    if st.button("Volver a comprobarlo todo", key="pxa_recomprobar_todo"):
        st.session_state["bloques_estado"] = {}
        _refrescar_estado_equipo()
        st.rerun()

    cache: dict[str, list[lecturas.Fila]] = st.session_state["bloques_estado"]
    for bloque in lecturas.BLOQUES:
        # Carga perezosa por bloque: los rápidos se consultan al entrar; el de
        # seguridad del dispositivo espera a que lo pidas (§14).
        if bloque.id not in cache and not bloque.perezoso:
            cache[bloque.id] = lecturas.consultar_bloque(bloque.id)
        filas = cache.get(bloque.id)

        with st.container(key=f"pxa_bloque_{bloque.id}"):
            meta = f"{len(filas)} comprobaciones" if filas else "sin consultar"
            st.markdown(
                f'<div class="pxa-bloque-cabecera"><span class="pxa-microlabel">{_e(bloque.titulo)}</span>'
                f'<span class="pxa-bloque-meta pxa-tabular">{_e(meta)}</span></div>',
                unsafe_allow_html=True,
            )
            if filas is None:
                st.markdown(
                    f'<div class="pxa-bloque-pendiente"><div class="pxa-bloque-pendiente-texto">'
                    f"<div>Sin consultar todavía</div><div>{_e(bloque.nota)}</div></div></div>",
                    unsafe_allow_html=True,
                )
                if st.button("Consultar ahora", key=f"pxa_consultar_{bloque.id}"):
                    cache[bloque.id] = lecturas.consultar_bloque(bloque.id)
                    st.rerun()
                continue

            cuerpo = "".join(
                f'<div class="pxa-estado-fila"><span class="pxa-estado-etiqueta">{_e(fila.etiqueta)}</span>'
                f'<span class="pxa-estado-valor pxa-valor-{fila.estilo}">{_e(fila.valor)}</span></div>'
                for fila in filas
            )
            st.markdown(
                f'<div class="pxa-bloque-tabla">{cuerpo}'
                f'<div class="pxa-bloque-pie"><span class="pxa-bloque-pregunta">{_e(bloque.pregunta)}</span>'
                f'<span class="pxa-bloque-nota">{_e(bloque.nota)}</span></div></div>',
                unsafe_allow_html=True,
            )


def _pantalla_auditoria() -> None:
    filtro = st.session_state["filtro_auditoria"]
    lista = auditoria.entradas(desde=st.session_state["inicio_sesion"], solo_sin_hacer=filtro == "sin_hacer")
    completa = auditoria.entradas(desde=st.session_state["inicio_sesion"])
    total, hechas, sin_hacer = auditoria.recuento(completa)

    _cabecera_pantalla(
        "Registro de la sesión",
        "Todo lo que he intentado hacer queda aquí, lo hiciera o no. "
        f'<span class="pxa-tabular">{total}</span> entradas: '
        f'<span class="pxa-tabular">{hechas}</span> hechas, '
        f'<span class="pxa-tabular">{sin_hacer}</span> sin hacer.',
        "auditoria",
    )

    col_todo, col_sin, _ = st.columns([1, 1, 3])
    with col_todo:
        if st.button("Todo", key=f"pxa_filtro_todo_{'on' if filtro == 'todo' else 'off'}", use_container_width=True):
            st.session_state["filtro_auditoria"] = "todo"
            st.rerun()
    with col_sin:
        if st.button(
            "Solo sin hacer",
            key=f"pxa_filtro_sinhacer_{'on' if filtro == 'sin_hacer' else 'off'}",
            use_container_width=True,
        ):
            st.session_state["filtro_auditoria"] = "sin_hacer"
            st.rerun()

    if not lista:
        st.caption("Todavía no hay nada registrado en esta sesión.")
    for indice, entrada in enumerate(lista):
        with st.container(key=f"pxa_aud_{indice}"):
            clase = "pxa-aud-hecha" if entrada.hecha else "pxa-aud-sin-hacer"
            st.markdown(
                f'<div class="pxa-aud-fila {clase}">'
                f'<span class="pxa-aud-hora pxa-tabular">{_e(entrada.hora)}</span>'
                f'<span class="pxa-aud-marca">{entrada.marca}</span>'
                f'<span class="pxa-aud-cuerpo"><span class="pxa-aud-titulo">{_e(entrada.titulo)}</span>'
                f'<span class="pxa-aud-resultado">{_e(entrada.resultado)}</span></span>'
                f'<span class="pxa-aud-autor">{_e(entrada.autor)}</span>'
                f'<span class="pxa-aud-proveedor">{_e(entrada.proveedor)}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )
            with st.expander(f"Detalle de la entrada de las {entrada.hora}"):
                for etiqueta, valor in entrada.detalle:
                    st.markdown(
                        f'<div class="pxa-detalle-row"><span class="pxa-detalle-label">{_e(etiqueta)}</span>'
                        f'<span class="pxa-detalle-valor pxa-tabular">{_e(valor)}</span></div>',
                        unsafe_allow_html=True,
                    )
    st.markdown(f'<p class="pxa-nota-registro">{_e(auditoria.NOTA_REGISTRO)}</p>', unsafe_allow_html=True)


def _pantalla_catalogo() -> str | None:
    _cabecera_pantalla(
        "Qué puedes preguntarme",
        "Casi todo son consultas: las miro y te lo cuento. Las marcadas con "
        '<span class="pxa-punto">·</span> te pedirán permiso antes de tocar nada.',
        "catalogo",
    )
    elegida: str | None = None
    columnas = st.columns(2)
    for indice, (titulo, preguntas) in enumerate(textos.CATALOGO):
        with columnas[indice % 2]:
            with st.container(key=f"pxa_grupo_{indice}"):
                st.markdown(_microlabel(titulo), unsafe_allow_html=True)
                for j, (pregunta, pide_permiso) in enumerate(preguntas):
                    # El punto de "te pedirá permiso" lo pone el CSS, para poder
                    # pintarlo en color de acento sin tocar el texto del botón.
                    clase = "pxa_cat_permiso" if pide_permiso else "pxa_cat_lectura"
                    if st.button(pregunta, key=f"{clase}_{indice}_{j}", use_container_width=True):
                        elegida = pregunta
    return elegida


# ---------------------------------------------------------------------------
# Programa principal
# ---------------------------------------------------------------------------

def main() -> None:
    _inicializar_estado()
    _inyectar_estilos()

    if st.session_state["semaforo"] is None:
        _refrescar_estado_equipo()
    if st.session_state["sesion"] is None:
        st.session_state["sesion"] = lecturas.consultar_sesion()

    estado_actual: EstadoTurno | None = st.session_state["contenedor_estado"]["actual"]
    codigo_proveedor = _renderizar_sidebar(estado_actual)
    _asegurar_agente(codigo_proveedor)

    _renderizar_cabecera()

    pantalla = st.session_state["pantalla"]
    mensaje_pantalla: str | None = None
    if pantalla == "detalle":
        _pantalla_estado_detalle()
    elif pantalla == "auditoria":
        _pantalla_auditoria()
    elif pantalla == "catalogo":
        mensaje_pantalla = _pantalla_catalogo()

    mensaje_historial: str | None = None
    mensaje_sugerido: str | None = None
    if pantalla is None:
        historial = st.session_state["historial_ui"]
        for indice, entrada in enumerate(historial):
            pedido = _renderizar_entrada_historial(entrada, indice)
            mensaje_historial = pedido or mensaje_historial

        if not historial and st.session_state["hilo"] is None:
            mensaje_sugerido = _renderizar_bienvenida()

        if st.session_state["hilo"] is not None:
            _gestionar_turno_en_curso(codigo_proveedor)

    mensaje_reintentar = st.session_state.pop("reintentar_mensaje", None)
    hay_turno = st.session_state["hilo"] is not None
    deshabilitado = hay_turno or st.session_state["agente"] is None
    if estado_actual is not None and estado_actual.propuesta is not None:
        placeholder = "Responde arriba para seguir escribiendo"
    elif hay_turno:
        placeholder = "Termino esto y sigo contigo"
    else:
        placeholder = "Escribe tu pregunta o petición..."
    mensaje_escrito = st.chat_input(placeholder, disabled=deshabilitado)

    st.markdown(
        f'<div class="pxa-inputbar-caption"><span>{CONTRATO_ENTRADA}</span>'
        f'<span class="pxa-accion">{"En espera" if deshabilitado else "Enviar"}</span></div>',
        unsafe_allow_html=True,
    )

    mensaje = mensaje_reintentar or mensaje_pantalla or mensaje_historial or mensaje_sugerido or mensaje_escrito
    if mensaje and not hay_turno and st.session_state["agente"] is not None:
        st.session_state["pantalla"] = None
        st.session_state["aviso_sidebar"] = None
        st.session_state["historial_ui"].append({"role": "user", "content": mensaje})
        estado = EstadoTurno(mensaje=mensaje, proveedor=codigo_proveedor)
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
