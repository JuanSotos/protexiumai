"""Tablas de redacción en lenguaje llano de la interfaz.

Toda la copia que depende de una herramienta concreta vive aquí, en tablas de
datos, y no repartida por la vista: nombres en llano de las 25 herramientas
(ADDENDUM-02 §2), traducción de los siete motivos de rechazo (§3), plantillas del
indicador (§4), molde de errores del sistema (§5), textos de las operaciones
irreversibles (§6), alcance de las propuestas con parámetros (§7), vocabulario del
semáforo (§10), catálogo de preguntas y resultado sin datos (§13).

Módulo puro: sin dependencias de src/ ni de streamlit. Los valores técnicos que
traduce son los enums reales de executor.WHITELIST (profile, enabled,
allow_inbound_rules, ruta), no los del documento de diseño.
"""

from __future__ import annotations

import os
import re
from typing import Any, Callable

# ---------------------------------------------------------------------------
# §2 · Traducción a llano de los valores de parámetro
# ---------------------------------------------------------------------------

VALOR_PLANO: dict[str, str] = {
    # profile (set_firewall_profile, set_block_all_incoming)
    "Domain": "Red del trabajo",
    "Private": "Red de casa",
    "Public": "Redes públicas",
    # ruta (start_custom_scan)
    "Descargas": "Tu carpeta de Descargas",
    "Escritorio": "Tu Escritorio",
    "Documentos": "Tu carpeta de Documentos",
    # enabled / allow_inbound_rules
    "True": "sí",
    "False": "no",
}

# Carpeta real de Windows a la que apunta cada valor del enum `ruta`, para poder
# enseñar la ruta concreta en la fila "Sobre qué" (§7). Réplica de la tabla de
# rutas de la plantilla de start_custom_scan en executor.WHITELIST.
CARPETA_WINDOWS: dict[str, str] = {
    "Descargas": "Downloads",
    "Escritorio": "Desktop",
    "Documentos": "Documents",
}


def ruta_real(valor_ruta: str) -> str:
    """Ruta absoluta de la carpeta de usuario que analizará start_custom_scan."""
    carpeta = CARPETA_WINDOWS.get(valor_ruta)
    if carpeta is None:
        return ""
    return os.path.join(os.path.expanduser("~"), carpeta)


def _red(params: dict[str, Any]) -> str:
    perfil = str(params.get("profile", ""))
    return VALOR_PLANO.get(perfil, perfil or "esa red")


def _carpeta(params: dict[str, Any]) -> str:
    valor = str(params.get("ruta", ""))
    return VALOR_PLANO.get(valor, valor or "esa carpeta")


# Campos con nombre de las plantillas, ya traducidos a llano. Solo las tres
# herramientas cuyo nombre en llano varía con los parámetros necesitan resolutor.
_CAMPOS: dict[str, Callable[[dict[str, Any]], dict[str, str]]] = {
    "start_custom_scan": lambda p: {"carpeta": _carpeta(p)},
    "set_firewall_profile": lambda p: {
        "red": _red(p),
        "red_min": _red(p).lower(),
        "hecho": "encendido" if p.get("enabled") == "True" else "apagado",
        "gerundio": "encendiendo" if p.get("enabled") == "True" else "apagando",
    },
    "set_block_all_incoming": lambda p: {
        "red": _red(p),
        "red_min": _red(p).lower(),
        "hecho": "bloqueado" if p.get("allow_inbound_rules") == "False" else "restaurado",
        "gerundio": "bloqueando" if p.get("allow_inbound_rules") == "False" else "restaurando",
    },
}

# ---------------------------------------------------------------------------
# §2 · Nombres en llano de las 25 herramientas, en las tres formas
# ---------------------------------------------------------------------------

NOMBRE_HECHO: dict[str, str] = {
    "get_defender_status": "He mirado el estado de Defender",
    "get_detected_threats": "He mirado si hay amenazas detectadas",
    "get_firewall_status": "He mirado el estado del firewall",
    "get_active_network_profile": "He mirado a qué red estás conectado",
    "get_account_info": "He mirado con qué cuenta has entrado",
    "get_allowed_threats": "He mirado qué amenazas permitiste tú",
    "get_defender_preferences": "He mirado los ajustes de Defender",
    "get_exploit_protection_status": "He mirado la protección contra exploits",
    "get_allowed_firewall_rules": "He mirado qué aplicaciones pueden entrar",
    "get_core_isolation_status": "He mirado el aislamiento del núcleo",
    "get_storage_status": "He mirado el espacio libre de los discos",
    "get_battery_status": "He mirado el estado de la batería",
    "get_time_service_status": "He mirado si la hora del equipo se sincroniza",
    "get_defender_exclusions": "He mirado qué carpetas quedan fuera del análisis",
    "get_secure_boot_status": "He mirado si el arranque seguro está activo",
    "get_tpm_status": "He mirado el chip de seguridad del equipo",
    "get_bitlocker_status": "He mirado si tus discos están cifrados",
    "start_quick_scan": "He analizado el equipo por encima",
    "start_full_scan": "He analizado el equipo entero",
    "start_custom_scan": "He analizado la carpeta {carpeta}",
    "update_signatures": "He actualizado las definiciones de virus",
    "set_firewall_profile": "He {hecho} el firewall en {red_min}",
    "set_block_all_incoming": "He {hecho} las conexiones entrantes en {red_min}",
    "remove_all_threats": "He eliminado las amenazas detectadas",
    "restore_firewall_defaults": "He restaurado las reglas del firewall de fábrica",
}

NOMBRE_SIN_HACER: dict[str, str] = {
    "get_defender_status": "No he podido mirar el estado de Defender",
    "get_detected_threats": "No he podido mirar las amenazas detectadas",
    "get_firewall_status": "No he podido mirar el estado del firewall",
    "get_active_network_profile": "No he podido mirar a qué red estás conectado",
    "get_account_info": "No he podido mirar con qué cuenta has entrado",
    "get_allowed_threats": "No he podido mirar qué amenazas permitiste tú",
    "get_defender_preferences": "No he podido mirar los ajustes de Defender",
    "get_exploit_protection_status": "No he podido mirar la protección contra exploits",
    "get_allowed_firewall_rules": "No he podido mirar qué aplicaciones pueden entrar",
    "get_core_isolation_status": "No he podido mirar el aislamiento del núcleo",
    "get_storage_status": "No he podido mirar el espacio libre de los discos",
    "get_battery_status": "No he podido mirar el estado de la batería",
    "get_time_service_status": "No he podido mirar si la hora del equipo se sincroniza",
    "get_defender_exclusions": "No he podido mirar qué carpetas quedan fuera del análisis",
    "get_secure_boot_status": "No he podido mirar si el arranque seguro está activo",
    "get_tpm_status": "No he podido mirar el chip de seguridad del equipo",
    "get_bitlocker_status": "No he podido mirar el cifrado del disco",
    "start_quick_scan": "No he analizado el equipo",
    "start_full_scan": "No he analizado el equipo entero",
    "start_custom_scan": "No he analizado la carpeta {carpeta}",
    "update_signatures": "No he actualizado las definiciones de virus",
    "set_firewall_profile": "No he {hecho} el firewall en {red_min}",
    "set_block_all_incoming": "No he {hecho} las conexiones entrantes en {red_min}",
    "remove_all_threats": "No he quitado ninguna amenaza",
    "restore_firewall_defaults": "No he restaurado las reglas del firewall",
}

NOMBRE_EN_CURSO: dict[str, str] = {
    "get_defender_status": "Estoy mirando el estado de Defender",
    "get_detected_threats": "Estoy mirando las amenazas detectadas",
    "get_firewall_status": "Estoy mirando el estado del firewall",
    "get_active_network_profile": "Estoy mirando a qué red estás conectado",
    "get_account_info": "Estoy mirando con qué cuenta has entrado",
    "get_allowed_threats": "Estoy mirando qué amenazas permitiste tú",
    "get_defender_preferences": "Estoy mirando los ajustes de Defender",
    "get_exploit_protection_status": "Estoy mirando la protección contra exploits",
    "get_allowed_firewall_rules": "Estoy mirando qué aplicaciones pueden entrar",
    "get_core_isolation_status": "Estoy mirando el aislamiento del núcleo",
    "get_storage_status": "Estoy mirando el espacio libre de los discos",
    "get_battery_status": "Estoy mirando el estado de la batería",
    "get_time_service_status": "Estoy mirando si la hora del equipo se sincroniza",
    "get_defender_exclusions": "Estoy mirando qué carpetas quedan fuera del análisis",
    "get_secure_boot_status": "Estoy mirando si el arranque seguro está activo",
    "get_tpm_status": "Estoy mirando el chip de seguridad del equipo",
    "get_bitlocker_status": "Estoy mirando si tus discos están cifrados",
    "start_quick_scan": "Estoy analizando el equipo por encima",
    "start_full_scan": "Estoy analizando el equipo entero",
    "start_custom_scan": "Estoy analizando la carpeta {carpeta}",
    "update_signatures": "Estoy actualizando las definiciones de virus",
    "set_firewall_profile": "Estoy {gerundio} el firewall en {red_min}",
    "set_block_all_incoming": "Estoy {gerundio} las conexiones entrantes en {red_min}",
    "remove_all_threats": "Estoy eliminando las amenazas detectadas",
    "restore_firewall_defaults": "Estoy restaurando las reglas del firewall de fábrica",
}

_FORMAS: dict[str, dict[str, str]] = {
    "hecho": NOMBRE_HECHO,
    "sin_hacer": NOMBRE_SIN_HACER,
    "en_curso": NOMBRE_EN_CURSO,
}


def frase(tool_id: str, params: dict[str, Any] | None = None, forma: str = "hecho") -> str:
    """Nombre en llano de una herramienta, con sus parámetros ya traducidos.

    forma: "hecho" (pasado), "sin_hacer" (negativo) o "en_curso" (gerundio).
    Si el tool_id no está en la tabla se devuelve el propio identificador: es la
    señal visible de que hay una herramienta sin redacción (lo cubre
    tests/test_textos.py).
    """
    plantilla = _FORMAS[forma].get(tool_id)
    if plantilla is None:
        return tool_id
    resolutor = _CAMPOS.get(tool_id)
    if resolutor is None:
        return plantilla
    return plantilla.format(**resolutor(params or {}))


# ---------------------------------------------------------------------------
# Normalización de la respuesta del modelo
# ---------------------------------------------------------------------------

_PATRON_BR = re.compile(r"<br\s*/?>", re.IGNORECASE)


def limpiar_respuesta(texto: str) -> str:
    """Convierte a Markdown real las etiquetas <br> que a veces devuelve el modelo.

    El texto del modelo se pinta SIEMPRE con el HTML escapado (nunca con
    unsafe_allow_html): puede arrastrar contenido procedente de la salida de una
    herramienta, que es un dato y no marcado de confianza. Por eso los saltos se
    traducen a Markdown en vez de dejarlos pasar como HTML.

    Dentro de una fila de tabla el salto no se puede convertir en un salto real
    —rompería la tabla—, así que ahí se sustituye por un separador visible.
    """
    if not texto:
        return ""
    lineas = []
    for linea in texto.splitlines():
        if linea.lstrip().startswith("|"):
            lineas.append(_PATRON_BR.sub(" · ", linea))
        else:
            # Dos espacios + salto: el salto duro de Markdown.
            lineas.append(_PATRON_BR.sub("  \n", linea))
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# §3 · Los siete motivos de rechazo, en llano
# ---------------------------------------------------------------------------

MOTIVO_RECHAZO: dict[str, str] = {
    "usuario_rechazo": "Sin hacer · me dijiste que no",
    "requiere_admin": "Sin hacer · hace falta abrir como administrador",
    "tool_id_desconocido": "Sin hacer · esa operación no está en mi lista",
    "parametro_no_declarado": "Sin hacer · me pedía un dato que no puedo aceptar",
    "parametro_faltante": "Sin hacer · faltaba un dato para poder ejecutarlo",
    "valor_fuera_de_enum": "Sin hacer · el valor pedido no es uno de los permitidos",
    "argumentos_invalidos": "Sin hacer · la petición no llegó en un formato que entienda",
}

MOTIVO_DESCONOCIDO = "Sin hacer · no ha llegado a ejecutarse"

# Quién autorizó (o impidió) cada paso, en el recibo y en la auditoría.
AUTOR_SIN_PERMISO = "sin permiso"
AUTOR_AUTORIZADO = "lo autorizaste tú"
AUTOR_RECHAZADO = "lo rechazaste tú"
AUTOR_SISTEMA = "límite del sistema"

# ---------------------------------------------------------------------------
# Etiquetas de nivel (la jerga accion/mutante no sale a la superficie)
# ---------------------------------------------------------------------------

NIVEL_PLANO: dict[str, str] = {
    "start_quick_scan": "Analiza el equipo",
    "start_full_scan": "Analiza el equipo",
    "start_custom_scan": "Analiza el equipo",
    "update_signatures": "Actualiza las defensas",
    "set_firewall_profile": "Cambia un ajuste",
    "set_block_all_incoming": "Cambia un ajuste",
    "restore_firewall_defaults": "Cambia un ajuste",
    "remove_all_threats": "Borra datos",
}

# ---------------------------------------------------------------------------
# §6 · Operaciones irreversibles
# ---------------------------------------------------------------------------

IRREVERSIBLES: tuple[str, ...] = ("remove_all_threats", "restore_firewall_defaults")

BOTON_SI: dict[str, str] = {
    "remove_all_threats": "Sí, bórralas",
    "restore_firewall_defaults": "Sí, restaura el firewall",
}
BOTON_SI_POR_DEFECTO = "Sí, adelante"

ENLACE_ALCANCE: dict[str, str] = {
    "remove_all_threats": "Ver qué se va a borrar",
    "restore_firewall_defaults": "Ver qué reglas se pierden",
}

NOTA_IRREVERSIBLE: dict[str, str] = {
    "remove_all_threats": (
        "Esto no se puede deshacer. Si prefieres verlas antes, pídemelo y te las "
        "enseño una a una sin tocar nada."
    ),
    "restore_firewall_defaults": (
        "Esto no se puede deshacer. Si prefieres ver antes qué reglas hay, pídemelo "
        "y te las enseño una a una sin tocar nada."
    ),
}

ROTULO_PERMISO = "Necesito tu permiso"
ROTULO_PERMISO_IRREVERSIBLE = "Necesito tu permiso · esto no se deshace"
ETIQUETA_SIN_VUELTA = "Sin vuelta atrás"

# ---------------------------------------------------------------------------
# §7 · "Sobre qué" · alcance de cada propuesta, en llano
# ---------------------------------------------------------------------------

_ALCANCE_RED: dict[str, str] = {
    "Public": "Solo el perfil de redes públicas. Tu red de casa y la del trabajo se quedan como están.",
    "Private": "Solo el perfil de tu red de casa. Las redes públicas y la del trabajo se quedan como están.",
    "Domain": "Solo el perfil de la red del trabajo. Tu red de casa y las redes públicas se quedan como están.",
}


def alcance(tool_id: str, params: dict[str, Any] | None = None, detalle: str | None = None) -> str:
    """Fila "Sobre qué" de la tarjeta de permiso (§7).

    detalle es el alcance real leído del equipo (las amenazas en cuarentena o las
    reglas de entrada activas) cuando la UI ha podido consultarlo; si no hay dato,
    se cae a una descripción genérica, nunca a un recuento inventado.
    """
    params = params or {}
    if tool_id == "start_custom_scan":
        ruta = ruta_real(str(params.get("ruta", "")))
        carpeta = _carpeta(params)
        return f"{carpeta} · {ruta}" if ruta else carpeta
    if tool_id == "set_firewall_profile":
        return _ALCANCE_RED.get(str(params.get("profile", "")), "Un perfil del firewall.")
    if tool_id == "set_block_all_incoming":
        red = _red(params)
        if params.get("allow_inbound_rules") == "False":
            return f"{red} · se bloquean también las apps que hoy tienen permiso"
        return f"{red} · vuelven a valer los permisos que ya tenías"
    if tool_id == "remove_all_threats":
        return detalle or "Las amenazas que Defender tiene ahora mismo en cuarentena"
    if tool_id == "restore_firewall_defaults":
        base = "Todas las reglas del firewall, incluidas las que hayas creado tú"
        return f"{base} · {detalle}" if detalle else base
    if tool_id in ("start_quick_scan", "start_full_scan"):
        return "Todo el equipo"
    if tool_id == "update_signatures":
        return "Las definiciones de virus de Windows Defender"
    return "Tu equipo"


# ---------------------------------------------------------------------------
# Titular de la tarjeta de permiso, en primera persona
# ---------------------------------------------------------------------------

_TITULAR_PROPUESTA: dict[str, str] = {
    "start_quick_scan": "Voy a analizar el equipo por encima",
    "start_full_scan": "Voy a analizar el equipo entero",
    "start_custom_scan": "Voy a analizar {carpeta}",
    "update_signatures": "Voy a actualizar las definiciones de virus de Windows Defender",
    "remove_all_threats": "Voy a eliminar las amenazas que ha encontrado Defender",
    "restore_firewall_defaults": "Voy a dejar el firewall con las reglas de fábrica",
}


def titular_propuesta(tool_id: str, params: dict[str, Any] | None = None, descripcion: str = "") -> str:
    """Lo que va a hacer, en llano y en primera persona (README §5).

    `descripcion` es la de executor.WHITELIST, escrita para el modelo; solo se usa
    como red de seguridad si aparece una herramienta sin titular propio.
    """
    params = params or {}
    if tool_id == "set_firewall_profile":
        verbo = "encender" if params.get("enabled") == "True" else "apagar"
        return f"Voy a {verbo} el firewall cuando te conectes a {_red(params).lower()}"
    if tool_id == "set_block_all_incoming":
        if params.get("allow_inbound_rules") == "False":
            return f"Voy a bloquear todas las conexiones entrantes en {_red(params).lower()}"
        return f"Voy a volver a permitir las conexiones entrantes normales en {_red(params).lower()}"
    plantilla = _TITULAR_PROPUESTA.get(tool_id)
    if plantilla is None:
        return descripcion or "Voy a cambiar un ajuste de seguridad de tu equipo"
    if tool_id == "start_custom_scan":
        return plantilla.format(carpeta=_carpeta(params).lower())
    return plantilla


# ---------------------------------------------------------------------------
# Filas "Qué consigues" / "Se deshace"
# ---------------------------------------------------------------------------

def consigue_y_deshace(tool_id: str, params: dict[str, Any] | None = None) -> tuple[str, str]:
    """Texto en llano de las filas "Qué consigues" y "Se deshace"."""
    params = params or {}
    sin_cambios = "No hace falta: solo analiza, no cambia nada en tu equipo."
    if tool_id == "start_quick_scan":
        return "Revisa las carpetas y procesos más expuestos en unos minutos.", sin_cambios
    if tool_id == "start_full_scan":
        return "Revisa todo el equipo a fondo; puede tardar bastante rato.", sin_cambios
    if tool_id == "start_custom_scan":
        return f"Revisa solo {_carpeta(params).lower()}.", sin_cambios
    if tool_id == "update_signatures":
        return (
            "Descarga las definiciones de virus más recientes para detectar amenazas nuevas.",
            "No hace falta deshacerlo: solo añade información, no quita nada.",
        )
    if tool_id == "set_firewall_profile":
        if params.get("enabled") == "True":
            consigue = f"Tu equipo volverá a filtrar las conexiones cuando estés en {_red(params).lower()}."
        else:
            consigue = f"Tu equipo dejará de filtrar las conexiones en {_red(params).lower()}."
        return consigue, "Sí. Pídeme lo contrario y lo cambio de vuelta."
    if tool_id == "set_block_all_incoming":
        if params.get("allow_inbound_rules") == "False":
            consigue = f"Bloquea toda entrada de datos en {_red(params).lower()}, incluidas las apps permitidas."
        else:
            consigue = f"Vuelve a permitir la entrada normal en {_red(params).lower()}."
        return consigue, "Sí. Pídeme que lo revierta y vuelvo al comportamiento normal."
    if tool_id == "remove_all_threats":
        return (
            "Los archivos infectados desaparecen del equipo en lugar de seguir aislados en cuarentena.",
            "No. Una vez borrados no puedo recuperarlos.",
        )
    if tool_id == "restore_firewall_defaults":
        return (
            "Deja el firewall exactamente como venía de fábrica, sin reglas añadidas por nadie.",
            "No. Las reglas que hubieras creado tú se pierden.",
        )
    return "Cambia la configuración de seguridad de tu equipo.", "Consulta el detalle técnico."


# ---------------------------------------------------------------------------
# §4 · Indicador de estado y bloque "ejecutando"
# ---------------------------------------------------------------------------

COLETILLA_LECTURA = "solo miro, no cambio nada"

EXPECTATIVA_EJECUCION: dict[str, str] = {
    "start_quick_scan": (
        "Un análisis rápido suele tardar unos diez minutos. Puedes seguir usando el "
        "ordenador; te aviso al terminar."
    ),
    "start_custom_scan": (
        "Analizar una carpeta suele tardar hasta un cuarto de hora. Puedes seguir "
        "usando el ordenador; te aviso al terminar."
    ),
    "start_full_scan": (
        "Un análisis completo puede tardar hasta una hora. Puedes seguir usando el "
        "ordenador; te aviso al terminar."
    ),
    "update_signatures": "Descargar las definiciones suele tardar un par de minutos.",
}
EXPECTATIVA_POR_DEFECTO = "Es un cambio inmediato: unos segundos."

TIEMPO_AGOTADO_TITULAR = "El análisis sigue en marcha por su cuenta"
TIEMPO_AGOTADO_TEXTO = (
    "He dejado de esperar, pero Windows lo sigue haciendo en segundo plano. No es un "
    "fallo tuyo ni del equipo: pregúntame dentro de un rato y miro cómo ha quedado."
)

# ---------------------------------------------------------------------------
# §5 · Molde de los errores del sistema
# ---------------------------------------------------------------------------

TRANQUILIDAD_SISTEMA = "Tu equipo sigue igual de protegido y no he cambiado nada."
TRANQUILIDAD_PROVEEDOR = (
    "Tu equipo sigue igual de protegido. Esto solo afecta a nuestra conversación, no a tu seguridad."
)
ROTULO_FALLO = "No he podido terminar"

# Respuesta literal con la que src/agent.py cierra un turno que agotó
# MAX_ITERACIONES_POR_TURNO. tests/test_textos.py comprueba que sigue siendo esta.
RESPUESTA_SIN_CONVERGENCIA = (
    "No he podido completar la solicitud tras varios intentos; por favor, reformula la pregunta."
)

ERRORES_SISTEMA: dict[str, tuple[str, str]] = {
    "timeout": (
        "El equipo ha tardado más de lo que puedo esperar",
        "Solo se ha quedado a medias la consulta que te iba a responder.",
    ),
    "powershell_no_encontrado": (
        "No encuentro PowerShell en el equipo",
        "Sin PowerShell no puedo consultar nada; suele arreglarse reiniciando Windows.",
    ),
    "salida_ilegible": (
        "No he entendido lo que me ha devuelto el equipo",
        "La respuesta llegó en un formato que no sé leer; puedo intentarlo otra vez.",
    ),
    "requiere_elevacion": (
        "Esto necesita abrir la app como administrador",
        "No he cambiado nada. Nunca te pediré la contraseña.",
    ),
    "sin_convergencia": (
        "Me he liado dando vueltas y no he llegado a nada",
        "Prueba a preguntármelo de otra forma, más concreta.",
    ),
    "error_powershell": (
        "Windows me ha dado un error al ejecutar la orden",
        "El cambio no se ha aplicado; te dejo el error exacto en el detalle.",
    ),
}

# ---------------------------------------------------------------------------
# §9 · Estado de administrador de la sesión
# ---------------------------------------------------------------------------

SESION_CON_ADMIN = "Con administrador · Puedo consultarlo y hacerlo todo."
SESION_QUE_SIGNIFICA = (
    "Windows reserva algunas consultas y todos los cambios a las sesiones de "
    "administrador. ProtexiumAI nunca eleva permisos por su cuenta, nunca lanza un "
    "aviso de control de cuentas y nunca te pedirá tu contraseña: si quieres "
    "autorizar esas operaciones, cierra la app y vuelve a abrirla como administrador."
)
AVISO_ADMIN_PERMISO = (
    "Ahora mismo la sesión es de usuario estándar. Cierra ProtexiumAI y vuelve a "
    "abrirlo como administrador para poder autorizarlo. No te pediré nunca tu contraseña."
)

# ---------------------------------------------------------------------------
# §10 · Vocabulario del semáforo. `ondas` y `discontinuo` gobiernan la animación.
# ---------------------------------------------------------------------------

SEMAFORO: dict[str, dict[str, Any]] = {
    "protegido": {
        "titular": "Equipo protegido",
        "nota": "Defender y el firewall están activos",
        "color": "var(--p-ok)",
        "ondas": True,
        "discontinuo": False,
    },
    "atencion": {
        "titular": "Requiere atención",
        "nota": "",  # el motivo concreto lo pone quien calcula el estado
        "color": "var(--p-warn)",
        "ondas": True,
        "discontinuo": False,
    },
    "pasivo": {
        "titular": "Protegido por otro antivirus",
        "nota": "Defender está en segundo plano porque tienes otro antivirus instalado",
        "color": "var(--p-ok)",
        "ondas": True,
        "discontinuo": True,
    },
    "sin_vigilancia": {
        "titular": "Sin protección en tiempo real",
        "nota": "Nadie está revisando los archivos que abres",
        "color": "var(--p-bad)",
        "ondas": True,
        "discontinuo": False,
    },
    "sin_dato": {
        "titular": "No he podido comprobarlo",
        "nota": "La consulta no ha respondido. Vuelve a intentarlo.",
        "color": "var(--p-mute)",
        "ondas": False,
        "discontinuo": False,
    },
}

# ---------------------------------------------------------------------------
# §12 · Conversación nueva
# ---------------------------------------------------------------------------

AVISO_CAMBIO_PROVEEDOR = "Si cambias de sitio, empiezo una conversación nueva."
AVISO_CONVERSACION_NUEVA = "Empiezo de cero. El registro de lo que he hecho se conserva."

# ---------------------------------------------------------------------------
# §13 · Resultado sin datos: los cuatro trabajos que no devuelven informe
# ---------------------------------------------------------------------------

SIN_DATOS_AL_TERMINAR: dict[str, dict[str, str]] = {
    "start_quick_scan": {
        "titular": "Ya está: el análisis rápido ha terminado sin encontrar nada.",
        "parrafo": (
            "Windows no devuelve un informe al acabar, solo confirma que ha ido bien. Si "
            "quieres estar seguro, puedo mirar ahora la lista de amenazas detectadas."
        ),
        "boton": "¿Ha encontrado algo?",
        "pregunta": "¿Qué amenazas has detectado?",
    },
    "start_full_scan": {
        "titular": "Ya está: el análisis completo ha terminado sin encontrar nada.",
        "parrafo": (
            "Windows no devuelve un informe al acabar, solo confirma que ha ido bien. Si "
            "quieres estar seguro, puedo mirar ahora la lista de amenazas detectadas."
        ),
        "boton": "¿Ha encontrado algo?",
        "pregunta": "¿Qué amenazas has detectado?",
    },
    "start_custom_scan": {
        "titular": "Ya está: he analizado la carpeta y no ha salido nada.",
        "parrafo": (
            "Windows no devuelve un informe al acabar, solo confirma que ha ido bien. Si "
            "quieres estar seguro, puedo mirar ahora la lista de amenazas detectadas."
        ),
        "boton": "¿Ha encontrado algo?",
        "pregunta": "¿Qué amenazas has detectado?",
    },
    "update_signatures": {
        "titular": "Ya está: las definiciones de virus están al día.",
        "parrafo": (
            "Windows no devuelve un informe al terminar, solo confirma que la descarga ha "
            "ido bien. Si quieres, miro ahora de cuándo son las definiciones."
        ),
        "boton": "¿De cuándo son ahora?",
        "pregunta": "¿De cuándo son las definiciones de virus?",
    },
}

# ---------------------------------------------------------------------------
# Catálogo de preguntas. El segundo campo marca las que piden permiso.
# ---------------------------------------------------------------------------

CATALOGO: list[tuple[str, list[tuple[str, bool]]]] = [
    (
        "Windows Defender",
        [
            ("¿Cómo está mi PC?", False),
            ("¿Tengo algún virus detectado?", False),
            ("¿Están al día las definiciones?", False),
            ("Analiza mi carpeta de Descargas", True),
            ("Actualiza las definiciones de virus", True),
        ],
    ),
    (
        "Firewall y red",
        [
            ("¿Tengo el firewall encendido?", False),
            ("¿A qué red estoy conectado?", False),
            ("¿Qué aplicaciones pueden entrar?", False),
            ("Enciende el firewall en redes públicas", True),
        ],
    ),
    (
        "Seguridad del dispositivo",
        [
            ("¿Está cifrado mi disco?", False),
            ("¿Tengo el arranque seguro activado?", False),
            ("¿Mi equipo tiene chip de seguridad?", False),
            ("¿Está protegido el núcleo del sistema?", False),
        ],
    ),
    (
        "Rendimiento y salud",
        [
            ("¿Me queda espacio en el disco?", False),
            ("¿Cómo está la batería?", False),
            ("¿Tiene el equipo la hora bien puesta?", False),
        ],
    ),
    (
        "Si algo va mal",
        [
            ("Me ha salido una alerta rara", False),
            ("¿Por qué va lento mi ordenador?", False),
            ("Analiza el equipo entero", True),
            ("Quita las amenazas que has encontrado", True),
        ],
    ),
    (
        "Sobre lo que haces",
        [
            ("¿Qué has hecho en esta sesión?", False),
            ("¿Qué puedes cambiar sin preguntarme?", False),
            ("¿Sale algo de mi ordenador?", False),
        ],
    ),
]

SUGERENCIAS: list[str] = [
    "¿Cómo está mi PC?",
    "Me ha salido una alerta rara",
    "¿Está cifrado mi disco?",
]

# §11 · Marca de proveedor por turno
PROVEEDOR_TURNO: dict[str, str] = {
    "groq": "· respondido en la nube",
    "ollama": "· respondido en este equipo",
}
PROVEEDOR_AUDITORIA: dict[str, str] = {"groq": "Nube", "ollama": "Local"}
