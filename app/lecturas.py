"""Lecturas del equipo para el semáforo y la pantalla "Estado del equipo en detalle".

Solo consulta herramientas de nivel `lectura` a través de `executor.execute`, que
es quien valida, ejecuta y audita. Aquí no hay ningún subprocess ni ningún cmdlet:
este módulo únicamente traduce la salida de PowerShell a filas en lenguaje llano.

Los cinco bloques (ADDENDUM-02 §9, §10 y §14) se consultan de forma perezosa, uno
a uno, porque cuatro de las lecturas del bloque "Seguridad del dispositivo"
necesitan administrador y tardan varios segundos.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable

from app import textos
from src import executor

# ---------------------------------------------------------------------------
# Tipos
# ---------------------------------------------------------------------------

# Estilos de fila: valor normal, valor que pide atención, lectura reservada a
# administrador y dato que no aplica a este equipo (§9).
ESTILO_OK = "ok"
ESTILO_WARN = "warn"
ESTILO_ADMIN = "admin"
ESTILO_NA = "na"

VALOR_ADMIN = "Necesito administrador"
VALOR_SIN_DATO = "No he podido comprobarlo"


@dataclass(frozen=True)
class Fila:
    """Una comprobación ya traducida: etiqueta a la izquierda, valor a la derecha."""

    etiqueta: str
    valor: str
    estilo: str = ESTILO_OK


@dataclass(frozen=True)
class Bloque:
    """Un grupo de comprobaciones de la pantalla de estado en detalle."""

    id: str
    titulo: str
    pregunta: str
    nota: str
    herramientas: tuple[str, ...]
    construir: Callable[[dict[str, dict[str, Any]]], list[Fila]] = field(repr=False)
    perezoso: bool = False


# ---------------------------------------------------------------------------
# Helpers de formato
# ---------------------------------------------------------------------------

_PATRON_FECHA_DOTNET = re.compile(r"^/Date\((-?\d+)\)/$")

_MESES_ROMANOS = {
    1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI",
    7: "VII", 8: "VIII", 9: "IX", 10: "X", 11: "XI", 12: "XII",
}


def fecha_dotnet(valor: Any) -> datetime | None:
    """PowerShell serializa los DateTime como /Date(ms_epoch)/ vía ConvertTo-Json."""
    coincidencia = _PATRON_FECHA_DOTNET.match(str(valor))
    if not coincidencia:
        return None
    return datetime.fromtimestamp(int(coincidencia.group(1)) / 1000)


def fecha_legible(momento: datetime) -> str:
    return f"{momento.day} {_MESES_ROMANOS[momento.month]}, {momento:%H:%M}"


def fecha_romana(momento: datetime) -> str:
    """Fecha de la cabecera de sesión: 31 · VIII · 2026."""
    return f"{momento.day} · {_MESES_ROMANOS[momento.month]} · {momento.year}"


def _hace_cuanto(momento: datetime) -> str:
    dias = (datetime.now() - momento).days
    if dias <= 0:
        return "Hoy"
    if dias == 1:
        return "Ayer"
    return f"Hace {dias} días"


def _gigas(bytes_: Any) -> float:
    try:
        return float(bytes_) / (1024 ** 3)
    except (TypeError, ValueError):
        return 0.0


def _lista(datos: Any) -> list[Any]:
    if datos is None:
        return []
    if isinstance(datos, list):
        return datos
    return [datos]


def _sin_admin(tool_id: str) -> bool:
    """True si la herramienta necesita elevación y la sesión no la tiene."""
    spec = executor.WHITELIST.get(tool_id)
    return bool(spec is not None and spec.requiere_admin) and not executor._es_administrador()


def _datos(resultados: dict[str, dict[str, Any]], tool_id: str) -> Any | None:
    """Datos de una lectura si salió bien; None si falló o si faltó administrador."""
    resultado = resultados.get(tool_id)
    if resultado is None or not resultado.get("ok"):
        return None
    return resultado.get("data")


def _fila_fallida(etiqueta: str, tool_id: str) -> Fila:
    """Fila para una lectura que no ha dado dato: por elevación o por error."""
    if _sin_admin(tool_id):
        return Fila(etiqueta, VALOR_ADMIN, ESTILO_ADMIN)
    return Fila(etiqueta, VALOR_SIN_DATO, ESTILO_NA)


def _si_no(activo: Any, si: str, no: str) -> tuple[str, str]:
    return (si, ESTILO_OK) if activo else (no, ESTILO_WARN)


# ---------------------------------------------------------------------------
# Traducción de los enums numéricos de Windows
# ---------------------------------------------------------------------------

_CONTROLLED_FOLDER = {0: ("Desactivado", ESTILO_WARN), 1: ("Activado", ESTILO_OK), 2: ("Solo auditoría", ESTILO_WARN)}
_MAPS = {0: ("Desactivada", ESTILO_WARN), 1: ("Activada · nivel básico", ESTILO_OK), 2: ("Activada", ESTILO_OK)}
_MUESTRAS = {
    0: ("Me pregunta cada vez", ESTILO_OK),
    1: ("Solo muestras seguras", ESTILO_OK),
    2: ("Nunca envía muestras", ESTILO_OK),
    3: ("Envía todas las muestras", ESTILO_WARN),
}
_PUA = {0: ("Desactivado", ESTILO_WARN), 1: ("Activado", ESTILO_OK), 2: ("Solo auditoría", ESTILO_WARN)}
_CATEGORIA_RED = {0: "Redes públicas", 1: "Red de casa", 2: "Red del trabajo"}
# Get-Service: 4 = Running, 1 = Stopped
_ESTADO_SERVICIO = {4: ("En marcha", ESTILO_OK), 1: ("Parado", ESTILO_WARN)}
# Win32_DeviceGuard.SecurityServicesRunning
_SERVICIOS_NUCLEO = {1: "Credential Guard", 2: "Integridad de memoria", 3: "Arranque seguro del hipervisor"}


def _enum(tabla: dict[int, tuple[str, str]], valor: Any, por_defecto: str = "Sin dato") -> tuple[str, str]:
    try:
        return tabla[int(valor)]
    except (TypeError, ValueError, KeyError):
        return (por_defecto, ESTILO_NA)


# ---------------------------------------------------------------------------
# Bloque 1 · Windows Defender
# ---------------------------------------------------------------------------

def _filas_defender(r: dict[str, dict[str, Any]]) -> list[Fila]:
    filas: list[Fila] = []
    estado = _datos(r, "get_defender_status") or {}

    if estado:
        filas.append(Fila("Vigilancia en tiempo real", *_si_no(estado.get("RealTimeProtectionEnabled"), "Activada", "Desactivada")))
        filas.append(Fila("Antivirus", *_si_no(estado.get("AntivirusEnabled"), "Activado", "Desactivado")))
        filas.append(Fila("Servicio de Defender", *_si_no(estado.get("AMServiceEnabled"), "En marcha", "Parado")))

        firmas = fecha_dotnet(estado.get("AntivirusSignatureLastUpdated"))
        if firmas is None:
            filas.append(Fila("Firmas de virus", "Sin dato", ESTILO_NA))
        else:
            dias = (datetime.now() - firmas).days
            texto = f"Al día · {fecha_legible(firmas)}" if dias <= 7 else f"{_hace_cuanto(firmas)} · {fecha_legible(firmas)}"
            filas.append(Fila("Firmas de virus", texto, ESTILO_OK if dias <= 7 else ESTILO_WARN))

        for etiqueta, clave, limite in (
            ("Último análisis rápido", "QuickScanEndTime", 14),
            ("Último análisis completo", "FullScanEndTime", 30),
        ):
            momento = fecha_dotnet(estado.get(clave))
            if momento is None:
                filas.append(Fila(etiqueta, "Nunca", ESTILO_WARN))
            else:
                dias = (datetime.now() - momento).days
                filas.append(Fila(etiqueta, _hace_cuanto(momento), ESTILO_OK if dias <= limite else ESTILO_WARN))
    else:
        filas.append(_fila_fallida("Estado de Defender", "get_defender_status"))

    amenazas = r.get("get_detected_threats")
    if amenazas is not None and amenazas.get("ok"):
        detectadas = _lista(amenazas.get("data"))
        if detectadas:
            filas.append(Fila("Amenazas detectadas", f"{len(detectadas)} en cuarentena", ESTILO_WARN))
        else:
            filas.append(Fila("Amenazas detectadas", "Ninguna", ESTILO_OK))
    else:
        filas.append(_fila_fallida("Amenazas detectadas", "get_detected_threats"))

    ajustes = _datos(r, "get_defender_preferences")
    if ajustes:
        filas.append(Fila("Protección en la nube", *_enum(_MAPS, ajustes.get("MAPSReporting"))))
        filas.append(Fila("Envío de muestras", *_enum(_MUESTRAS, ajustes.get("SubmitSamplesConsent"))))
        filas.append(Fila("Acceso controlado a carpetas", *_enum(_CONTROLLED_FOLDER, ajustes.get("EnableControlledFolderAccess"))))
        filas.append(Fila("Bloqueo de apps no deseadas", *_enum(_PUA, ajustes.get("PUAProtection"))))
    else:
        filas.append(_fila_fallida("Ajustes de protección", "get_defender_preferences"))

    exclusiones = _datos(r, "get_defender_exclusions")
    if exclusiones is None:
        filas.append(_fila_fallida("Exclusiones configuradas", "get_defender_exclusions"))
    else:
        total = sum(
            len(_lista(exclusiones.get(clave)))
            for clave in ("ExclusionPath", "ExclusionExtension", "ExclusionProcess")
        )
        filas.append(
            Fila("Exclusiones configuradas", "Ninguna" if total == 0 else f"{total} configuradas", ESTILO_OK if total == 0 else ESTILO_WARN)
        )

    permitidas = _datos(r, "get_allowed_threats")
    if permitidas is None:
        filas.append(_fila_fallida("Amenazas que permitiste tú", "get_allowed_threats"))
    else:
        total = len(_lista(permitidas.get("ThreatIDDefaultAction_Ids")))
        filas.append(
            Fila("Amenazas que permitiste tú", "Ninguna" if total == 0 else f"{total} permitidas", ESTILO_OK if total == 0 else ESTILO_WARN)
        )
    return filas


# ---------------------------------------------------------------------------
# Bloque 2 · Firewall y red
# ---------------------------------------------------------------------------

_ETIQUETA_PERFIL = {
    "Private": "Red de casa (privada)",
    "Domain": "Red del trabajo (dominio)",
    "Public": "Redes públicas",
}


def _filas_firewall(r: dict[str, dict[str, Any]]) -> list[Fila]:
    filas: list[Fila] = []
    perfiles = {p.get("Name"): p for p in _lista(_datos(r, "get_firewall_status")) if isinstance(p, dict)}

    if perfiles:
        for nombre in ("Private", "Domain", "Public"):
            perfil = perfiles.get(nombre)
            if perfil is None:
                continue
            filas.append(Fila(_ETIQUETA_PERFIL[nombre], *_si_no(perfil.get("Enabled") == 1, "Encendido", "Apagado")))
    else:
        filas.append(_fila_fallida("Estado del firewall", "get_firewall_status"))

    activa = _lista(_datos(r, "get_active_network_profile"))
    if activa:
        red = activa[0] if isinstance(activa[0], dict) else {}
        categoria = _CATEGORIA_RED.get(red.get("NetworkCategory"), "Red desconocida")
        filas.append(Fila("Red activa ahora", f"{categoria} · {red.get('Name', 'sin nombre')}", ESTILO_OK))
    else:
        filas.append(_fila_fallida("Red activa ahora", "get_active_network_profile"))

    if perfiles:
        # AllowInboundRules: 0 = se bloquea todo lo entrante; 1 y 2 = se respetan
        # las reglas de aplicaciones permitidas.
        bloqueando = [_ETIQUETA_PERFIL[n] for n, p in perfiles.items() if n in _ETIQUETA_PERFIL and p.get("AllowInboundRules") == 0]
        if bloqueando:
            filas.append(Fila("Bloquea todas las entradas", "Sí · " + ", ".join(bloqueando), ESTILO_WARN))
        else:
            filas.append(Fila("Bloquea todas las entradas", "No", ESTILO_OK))
        avisa = all(p.get("NotifyOnListen") != 0 for p in perfiles.values())
        filas.append(Fila("Avisa al bloquear una app", *_si_no(avisa, "Sí", "No")))

    reglas = r.get("get_allowed_firewall_rules")
    if reglas is not None and reglas.get("ok"):
        filas.append(Fila("Reglas de entrada permitidas", f"{len(_lista(reglas.get('data')))} activas", ESTILO_OK))
    else:
        filas.append(_fila_fallida("Reglas de entrada permitidas", "get_allowed_firewall_rules"))
    return filas


# ---------------------------------------------------------------------------
# Bloque 3 · Seguridad del dispositivo (el lento, y el que pide administrador)
# ---------------------------------------------------------------------------

def _filas_dispositivo(r: dict[str, dict[str, Any]]) -> list[Fila]:
    filas: list[Fila] = []

    tpm = _datos(r, "get_tpm_status")
    if tpm is None:
        filas.append(_fila_fallida("Procesador de seguridad (TPM)", "get_tpm_status"))
    elif not tpm.get("TpmPresent"):
        filas.append(Fila("Procesador de seguridad (TPM)", "Este equipo no tiene TPM", ESTILO_NA))
    else:
        listo = bool(tpm.get("TpmReady") and tpm.get("TpmEnabled"))
        filas.append(Fila("Procesador de seguridad (TPM)", *_si_no(listo, "Presente y listo", "Presente, pero no está listo")))

    arranque = _datos(r, "get_secure_boot_status")
    if arranque is None or arranque.get("SecureBootEnabled") is None:
        filas.append(_fila_fallida("Arranque seguro", "get_secure_boot_status"))
    else:
        filas.append(Fila("Arranque seguro", *_si_no(arranque.get("SecureBootEnabled"), "Activado", "Desactivado")))

    volumenes = _lista(_datos(r, "get_bitlocker_status"))
    if not volumenes:
        filas.append(_fila_fallida("Cifrado del disco", "get_bitlocker_status"))
    else:
        for volumen in volumenes:
            if not isinstance(volumen, dict):
                continue
            punto = volumen.get("MountPoint", "?")
            protegido = volumen.get("ProtectionStatus") == 1
            porcentaje = volumen.get("EncryptionPercentage")
            valor = "Cifrado" if protegido else "Sin cifrar"
            if protegido and porcentaje is not None and int(porcentaje) < 100:
                valor = f"Cifrando · {porcentaje} %"
            filas.append(Fila(f"Cifrado del disco {punto}", *(_si_no(protegido, valor, valor))))

    nucleo = _datos(r, "get_core_isolation_status")
    if nucleo is None:
        filas.append(_fila_fallida("Aislamiento del núcleo", "get_core_isolation_status"))
    else:
        corriendo = [_SERVICIOS_NUCLEO[s] for s in _lista(nucleo.get("SecurityServicesRunning")) if s in _SERVICIOS_NUCLEO]
        if corriendo:
            filas.append(Fila("Aislamiento del núcleo", " · ".join(corriendo) + " en marcha", ESTILO_OK))
        else:
            filas.append(Fila("Aislamiento del núcleo", "Sin protecciones activas", ESTILO_WARN))

    exploits = _datos(r, "get_exploit_protection_status")
    if exploits is None:
        filas.append(_fila_fallida("Protección contra exploits", "get_exploit_protection_status"))
    else:
        # Windows expone estas mitigaciones como "valores por defecto" mientras nadie
        # las cambia; decir más de lo que dice el propio cmdlet sería inventar.
        origen = str(exploits.get("Source", ""))
        if origen.strip().lower() == "system defaults":
            filas.append(Fila("Protección contra exploits", "Con los valores por defecto de Windows", ESTILO_OK))
        else:
            filas.append(Fila("Protección contra exploits", f"Personalizada · {origen}", ESTILO_OK))
    return filas


# ---------------------------------------------------------------------------
# Bloque 4 · Rendimiento y salud
# ---------------------------------------------------------------------------

def _filas_salud(r: dict[str, dict[str, Any]]) -> list[Fila]:
    filas: list[Fila] = []

    discos = _lista(_datos(r, "get_storage_status"))
    if not discos:
        filas.append(_fila_fallida("Espacio libre", "get_storage_status"))
    for disco in discos:
        if not isinstance(disco, dict):
            continue
        libre, total = _gigas(disco.get("SizeRemaining")), _gigas(disco.get("Size"))
        proporcion = (libre / total) if total else 0
        filas.append(
            Fila(
                f"Espacio libre · Disco {disco.get('DriveLetter', '?')}:",
                f"{libre:.0f} GB libres de {total:.0f}",
                ESTILO_OK if proporcion >= 0.1 else ESTILO_WARN,
            )
        )

    bateria = r.get("get_battery_status")
    if bateria is not None and bateria.get("ok"):
        datos = bateria.get("data")
        if datos is None:
            # Documentado en la WHITELIST: sin batería no hay salida, y eso no es un fallo.
            filas.append(Fila("Batería", "Este equipo no tiene batería", ESTILO_NA))
        else:
            primera = _lista(datos)[0]
            carga = primera.get("EstimatedChargeRemaining") if isinstance(primera, dict) else None
            filas.append(Fila("Batería", f"{carga} % de carga" if carga is not None else "Presente", ESTILO_OK))
    else:
        filas.append(_fila_fallida("Batería", "get_battery_status"))

    hora = _datos(r, "get_time_service_status")
    if hora is None:
        filas.append(_fila_fallida("Servicio de hora de Windows", "get_time_service_status"))
    else:
        filas.append(Fila("Servicio de hora de Windows", *_enum(_ESTADO_SERVICIO, hora.get("Status"))))
    return filas


# ---------------------------------------------------------------------------
# Bloque 5 · Cuenta
# ---------------------------------------------------------------------------

def _filas_cuenta(r: dict[str, dict[str, Any]]) -> list[Fila]:
    cuenta = _datos(r, "get_account_info")
    if cuenta is None:
        return [_fila_fallida("Sesión iniciada como", "get_account_info")]
    admin = bool(cuenta.get("EsAdministradorLocal"))
    return [
        Fila("Sesión iniciada como", nombre_de_usuario(cuenta), ESTILO_OK),
        Fila(
            "Permisos",
            "Administrador local" if admin else "Usuario estándar · sin elevación",
            ESTILO_OK if admin else ESTILO_WARN,
        ),
    ]


def nombre_de_usuario(cuenta: dict[str, Any]) -> str:
    """Nombre corto de la cuenta: EQUIPO\\juan se muestra como juan."""
    usuario = str(cuenta.get("Usuario", ""))
    return usuario.split("\\")[-1] if usuario else "sin nombre"


# ---------------------------------------------------------------------------
# Catálogo de bloques
# ---------------------------------------------------------------------------

BLOQUES: tuple[Bloque, ...] = (
    Bloque(
        id="defender",
        titulo="Windows Defender",
        pregunta="Pregúntame por Defender",
        nota="Solo las exclusiones necesitan administrador",
        herramientas=(
            "get_defender_status",
            "get_detected_threats",
            "get_defender_preferences",
            "get_defender_exclusions",
            "get_allowed_threats",
        ),
        construir=_filas_defender,
    ),
    Bloque(
        id="firewall",
        titulo="Firewall y red",
        pregunta="Pregúntame por el firewall",
        nota="Encenderlo o apagarlo sí me pedirá permiso",
        herramientas=("get_firewall_status", "get_active_network_profile", "get_allowed_firewall_rules"),
        construir=_filas_firewall,
    ),
    Bloque(
        id="dispositivo",
        titulo="Seguridad del dispositivo",
        pregunta="Pregúntame por el cifrado y el arranque",
        nota="Cuatro de estas comprobaciones necesitan administrador y tardan unos segundos.",
        herramientas=(
            "get_tpm_status",
            "get_secure_boot_status",
            "get_bitlocker_status",
            "get_core_isolation_status",
            "get_exploit_protection_status",
        ),
        construir=_filas_dispositivo,
        perezoso=True,
    ),
    Bloque(
        id="salud",
        titulo="Rendimiento y salud",
        pregunta="Pregúntame por el espacio y la batería",
        nota="",
        herramientas=("get_storage_status", "get_battery_status", "get_time_service_status"),
        construir=_filas_salud,
    ),
    Bloque(
        id="cuenta",
        titulo="Cuenta",
        pregunta="Pregúntame por mis límites",
        nota="",
        herramientas=("get_account_info",),
        construir=_filas_cuenta,
    ),
)

BLOQUES_POR_ID: dict[str, Bloque] = {b.id: b for b in BLOQUES}


def consultar_bloque(bloque_id: str, proveedor: str | None = None) -> list[Fila]:
    """Ejecuta las lecturas de un bloque y devuelve sus filas ya traducidas."""
    bloque = BLOQUES_POR_ID[bloque_id]
    resultados = {tool_id: executor.execute(tool_id, {}, proveedor=proveedor) for tool_id in bloque.herramientas}
    return bloque.construir(resultados)


# ---------------------------------------------------------------------------
# Semáforo de cinco estados (§10)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Semaforo:
    """Estado del equipo tal y como lo muestra la barra lateral."""

    estado: str
    nota: str

    @property
    def titular(self) -> str:
        return str(textos.SEMAFORO[self.estado]["titular"])

    @property
    def color(self) -> str:
        return str(textos.SEMAFORO[self.estado]["color"])

    @property
    def ondas(self) -> bool:
        return bool(textos.SEMAFORO[self.estado]["ondas"])

    @property
    def discontinuo(self) -> bool:
        return bool(textos.SEMAFORO[self.estado]["discontinuo"])


def _redes_apagadas(perfiles: list[dict[str, Any]]) -> list[str]:
    return [
        textos.VALOR_PLANO.get(str(p.get("Name")), str(p.get("Name")))
        for p in perfiles
        if isinstance(p, dict) and p.get("Enabled") != 1
    ]


def calcular_semaforo(proveedor: str | None = None) -> tuple[Semaforo, dict[str, Any], dict[str, Any]]:
    """Consulta Defender y el firewall y deriva uno de los cinco estados del §10."""
    defender = executor.execute("get_defender_status", {}, proveedor=proveedor)
    firewall = executor.execute("get_firewall_status", {}, proveedor=proveedor)

    if not defender["ok"] or not firewall["ok"]:
        return Semaforo("sin_dato", str(textos.SEMAFORO["sin_dato"]["nota"])), defender, firewall

    datos = defender["data"] or {}
    perfiles = [p for p in _lista(firewall["data"]) if isinstance(p, dict)]
    apagadas = _redes_apagadas(perfiles)

    tiempo_real = bool(datos.get("RealTimeProtectionEnabled"))
    antivirus = bool(datos.get("AntivirusEnabled"))
    servicio = bool(datos.get("AMServiceEnabled"))

    if not tiempo_real and servicio and antivirus:
        # Heurística: el servicio sigue vivo y el antivirus registrado, pero no
        # vigila en tiempo real. Es el cuadro típico de Defender en modo pasivo.
        return Semaforo("pasivo", str(textos.SEMAFORO["pasivo"]["nota"])), defender, firewall
    if not tiempo_real:
        return Semaforo("sin_vigilancia", str(textos.SEMAFORO["sin_vigilancia"]["nota"])), defender, firewall
    if apagadas:
        nota = f"El firewall está apagado en {', '.join(apagadas).lower()}"
        return Semaforo("atencion", nota), defender, firewall
    if not antivirus:
        return Semaforo("atencion", "El antivirus de Defender está desactivado"), defender, firewall
    return Semaforo("protegido", str(textos.SEMAFORO["protegido"]["nota"])), defender, firewall


# ---------------------------------------------------------------------------
# Resumen de comprobaciones de la barra lateral
# ---------------------------------------------------------------------------

def filas_resumen(defender: dict[str, Any] | None, firewall: dict[str, Any] | None) -> list[tuple[str, str, str]]:
    """Las tres filas de comprobación de la barra lateral: (estilo, etiqueta, valor)."""
    datos = (defender or {}).get("data") or {} if (defender or {}).get("ok") else {}
    perfiles = [p for p in _lista((firewall or {}).get("data")) if isinstance(p, dict)] if (firewall or {}).get("ok") else []

    tiempo_real = bool(datos.get("RealTimeProtectionEnabled"))
    firmas = fecha_dotnet(datos.get("AntivirusSignatureLastUpdated"))
    if firmas is None:
        valor_firmas, estilo_firmas = "sin datos", ESTILO_NA
    else:
        dias = (datetime.now() - firmas).days
        valor_firmas = "al día" if dias <= 7 else _hace_cuanto(firmas).lower()
        estilo_firmas = ESTILO_OK if dias <= 7 else ESTILO_WARN
    activos = sum(1 for p in perfiles if p.get("Enabled") == 1)
    total = len(perfiles) if perfiles else 3

    return [
        (ESTILO_OK if tiempo_real else ESTILO_WARN, "Vigilancia en tiempo real", "activa" if tiempo_real else "inactiva"),
        (estilo_firmas, "Firmas de virus", valor_firmas),
        (ESTILO_OK if activos == total and total else ESTILO_WARN, "Firewall", f"{activos} de {total} redes"),
    ]


# ---------------------------------------------------------------------------
# §9 · Estado de administrador de la sesión
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Sesion:
    """Con qué cuenta se ha entrado y qué queda fuera de alcance por ello."""

    usuario: str
    es_admin: bool
    lecturas_bloqueadas: int
    acciones_bloqueadas: int

    @property
    def resumen(self) -> str:
        if self.es_admin:
            return textos.SESION_CON_ADMIN
        return (
            f"Como {self.usuario}, usuario estándar. {self.lecturas_bloqueadas} comprobaciones "
            f"y {self.acciones_bloqueadas} acciones no estarán disponibles."
        )


def consultar_sesion(proveedor: str | None = None) -> Sesion:
    """Lee la cuenta con get_account_info (lectura, sin elevación) y cuenta lo vetado.

    Los dos recuentos salen de la WHITELIST, no de una constante: si mañana cambia
    el catálogo, el texto de la barra lateral cambia con él.
    """
    resultado = executor.execute("get_account_info", {}, proveedor=proveedor)
    datos = resultado.get("data") or {} if resultado.get("ok") else {}
    es_admin = bool(datos.get("EsAdministradorLocal"))
    lecturas = sum(1 for s in executor.WHITELIST.values() if s.nivel == "lectura" and s.requiere_admin)
    acciones = sum(1 for s in executor.WHITELIST.values() if s.nivel != "lectura")
    return Sesion(
        usuario=nombre_de_usuario(datos) if datos else "esta cuenta",
        es_admin=es_admin,
        lecturas_bloqueadas=lecturas,
        acciones_bloqueadas=acciones,
    )
