"""Detección de capacidades del equipo: sistema operativo, versión, privilegios, binarios y MAC.

Todo es de solo lectura y sin `subprocess` (reglas 10 y 11 de `CLAUDE.md`): en Windows se lee el
registro con `winreg` en modo `KEY_READ` y se pregunta a la API si el usuario es administrador;
en Linux se parsea `/etc/os-release` y se consultan dos ficheros de `/sys`. El resultado es un
`Capacidades` inmutable que el catálogo usa para decidir qué entradas aplican al equipo
(`catalogo.aplicable`) y que el esquema del LLM usa para ofrecer solo herramientas útiles.

Nada de lo que se detecta es un dato personal: no se guarda el nombre de usuario ni el nombre
del equipo.
"""

from __future__ import annotations

import ctypes
import os
import re
import shutil
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable

from src import catalogo

# --- Constantes --------------------------------------------------------------------------
SO_WINDOWS = "windows"
SO_LINUX = "linux"
SO_OTRO = "otro"

FAMILIA_DESCONOCIDA = "desconocida"

MAC_APPARMOR = "apparmor"
MAC_SELINUX = "selinux"
MAC_NINGUNO = "ninguno"

# Primer build de Windows 11 (21H2); todo build igual o superior es Windows 11.
BUILD_MIN_WINDOWS_11 = 22000

CLAVE_VERSION_WINDOWS = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"

RUTAS_OS_RELEASE = (Path("/etc/os-release"), Path("/usr/lib/os-release"))
RUTA_APPARMOR = Path("/sys/module/apparmor/parameters/enabled")
RUTA_SELINUX = Path("/sys/fs/selinux/enforce")

# PATH fijo con el que se resuelven los binarios en Linux: es el mismo que usará el ejecutor
# (regla 10), de modo que la ruta absoluta detectada es la que se ejecutaría.
PATH_LINUX_FIJO = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# Familias de distribución por `ID` (o por cada elemento de `ID_LIKE`).
_IDS_POR_FAMILIA: dict[str, frozenset[str]] = {
    "debian": frozenset({"debian", "ubuntu", "kali", "linuxmint", "raspbian", "pop", "elementary", "zorin", "devuan"}),
    "rhel": frozenset({"rhel", "fedora", "centos", "rocky", "almalinux", "ol"}),
    "arch": frozenset({"arch", "manjaro", "endeavouros", "garuda", "artix"}),
    "suse": frozenset({"sles", "sled", "suse"}),
}

_PATRON_CLAVE_OS_RELEASE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


# --- Modelo de datos ---------------------------------------------------------------------
@dataclass(frozen=True)
class Capacidades:
    """Lo que el equipo ofrece: sistema, versión, privilegios, binarios resueltos y MAC.

    Los campos de un sistema que no es el detectado quedan en su valor neutro (`None`, `False`,
    cadena vacía). Los valores por defecto permiten construir un equipo simulado en los tests
    indicando solo lo relevante.
    """

    so: str = SO_OTRO
    # Windows (registro, HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion)
    windows_build: int | None = None
    windows_ubr: int | None = None
    windows_edicion: str = ""  # EditionID: Core (Home), Professional, Enterprise…
    windows_version: str = ""  # DisplayVersion: 23H2, 24H2…
    es_admin: bool = False
    # Linux (/etc/os-release)
    linux_id: str = ""
    linux_id_like: tuple[str, ...] = ()
    linux_version_id: str = ""
    linux_nombre: str = ""
    familia: str = FAMILIA_DESCONOCIDA  # debian | rhel | arch | suse | desconocida
    es_root: bool = False
    # Común
    binarios: dict[str, str | None] = field(default_factory=dict)  # nombre → ruta absoluta o None
    mac: str = MAC_NINGUNO  # apparmor | selinux | ninguno

    @property
    def es_windows11(self) -> bool:
        """True si es Windows con un build de Windows 11 (22000 o superior)."""
        return self.so == SO_WINDOWS and self.windows_build is not None and self.windows_build >= BUILD_MIN_WINDOWS_11

    @property
    def es_kali(self) -> bool:
        """True si la distribución Linux es Kali."""
        return self.so == SO_LINUX and self.linux_id == "kali"

    def a_dict(self) -> dict[str, Any]:
        """Vista serializable a JSON para el diagnóstico. Sin usuario ni nombre del equipo.

        Las rutas de los binarios que cuelgan del directorio personal se abrevian a `~` para no
        revelar el nombre de usuario.
        """
        datos: dict[str, Any] = {
            "so": self.so,
            "windows_build": self.windows_build,
            "windows_ubr": self.windows_ubr,
            "windows_edicion": self.windows_edicion,
            "windows_version": self.windows_version,
            "es_windows11": self.es_windows11,
            "es_admin": self.es_admin,
            "linux_id": self.linux_id,
            "linux_id_like": list(self.linux_id_like),
            "linux_version_id": self.linux_version_id,
            "linux_nombre": self.linux_nombre,
            "familia": self.familia,
            "es_kali": self.es_kali,
            "es_root": self.es_root,
            "mac": self.mac,
            "binarios": {nombre: _anonimizar_ruta(ruta) for nombre, ruta in self.binarios.items()},
        }
        return datos


def _anonimizar_ruta(ruta: str | None) -> str | None:
    """Sustituye el directorio personal por `~` en una ruta, para no exponer el usuario."""
    if ruta is None:
        return None
    casa = str(Path.home())
    if ruta.lower().startswith(casa.lower()):
        return "~" + ruta[len(casa) :]
    return ruta


# --- Sistema operativo -------------------------------------------------------------------
def _sistema_operativo() -> str:
    """Clasifica el sistema en el que corre el proceso: windows, linux u otro."""
    if sys.platform == "win32":
        return SO_WINDOWS
    if sys.platform.startswith("linux"):
        return SO_LINUX
    return SO_OTRO


# --- Windows -----------------------------------------------------------------------------
def _leer_registro_windows() -> dict[str, Any]:
    """Lee del registro (solo lectura) los valores de versión de Windows que existan.

    Devuelve un dict con las claves `CurrentBuildNumber`, `UBR`, `EditionID` y `DisplayVersion`
    que se hayan podido leer; las ausentes no aparecen. Si no hay `winreg` o la clave no abre,
    devuelve un dict vacío en lugar de lanzar una excepción.
    """
    try:
        import winreg  # solo existe en Windows
    except ImportError:
        return {}
    valores: dict[str, Any] = {}
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, CLAVE_VERSION_WINDOWS, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY
        ) as clave:
            for nombre in ("CurrentBuildNumber", "UBR", "EditionID", "DisplayVersion"):
                try:
                    valores[nombre] = winreg.QueryValueEx(clave, nombre)[0]
                except OSError:
                    continue
    except OSError:
        return {}
    return valores


def _es_administrador_windows() -> bool:
    """Comprueba con la API de Windows si el proceso tiene privilegios de administrador."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        return False


def _entero_o_none(valor: Any) -> int | None:
    """Convierte un valor del registro (texto o número) a entero; None si no es convertible."""
    try:
        return int(str(valor).strip())
    except (TypeError, ValueError):
        return None


def _texto_registro(valor: Any) -> str:
    """Normaliza un valor de texto del registro: cadena sin espacios, vacía si no es texto."""
    return valor.strip() if isinstance(valor, str) else ""


def _detectar_windows() -> dict[str, Any]:
    """Campos de `Capacidades` propios de Windows."""
    registro = _leer_registro_windows()
    return {
        "windows_build": _entero_o_none(registro.get("CurrentBuildNumber")),
        "windows_ubr": _entero_o_none(registro.get("UBR")),
        "windows_edicion": _texto_registro(registro.get("EditionID")),
        "windows_version": _texto_registro(registro.get("DisplayVersion")),
        "es_admin": _es_administrador_windows(),
    }


# --- Linux -------------------------------------------------------------------------------
def _valor_os_release(crudo: str) -> str | None:
    """Interpreta el valor de una línea de os-release; None si está mal formado.

    Admite comillas dobles (con escapes `\\"`, `\\\\`, `\\$` y `` \\` ``), comillas simples y
    valores sin comillas con comentario final (`ID=arch # nota`). Una comilla sin cerrar o
    texto tras la comilla de cierre invalidan la línea.
    """
    crudo = crudo.strip()
    if not crudo:
        return ""
    comilla = crudo[0]
    if comilla not in "\"'":
        return crudo.split(" #", 1)[0].split("\t#", 1)[0].strip()
    resultado: list[str] = []
    indice = 1
    while indice < len(crudo):
        caracter = crudo[indice]
        if caracter == "\\" and comilla == '"' and indice + 1 < len(crudo) and crudo[indice + 1] in '"\\$`':
            resultado.append(crudo[indice + 1])
            indice += 2
            continue
        if caracter == comilla:
            resto = crudo[indice + 1 :].strip()
            return "".join(resultado) if not resto or resto.startswith("#") else None
        resultado.append(caracter)
        indice += 1
    return None  # comilla sin cerrar


def parsear_os_release(texto: str) -> dict[str, str]:
    """Parsea el contenido de un fichero os-release a {clave: valor}.

    Ignora líneas vacías, comentarios y líneas mal formadas (sin `=`, clave inválida o comilla
    sin cerrar). Nunca lanza excepciones: un texto basura produce un dict vacío o parcial.
    """
    campos: dict[str, str] = {}
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, crudo = linea.partition("=")
        clave = clave.strip()
        if not _PATRON_CLAVE_OS_RELEASE.match(clave):
            continue
        valor = _valor_os_release(crudo)
        if valor is not None:
            campos[clave] = valor
    return campos


def familia_de_distribucion(identificador: str, id_like: Iterable[str]) -> str:
    """Familia (debian, rhel, arch, suse) según `ID` y, si no basta, `ID_LIKE`; si no, «desconocida»."""
    for candidato in (identificador, *id_like):
        candidato = candidato.strip().lower()
        if not candidato:
            continue
        if candidato.startswith("opensuse"):
            return "suse"
        for familia, ids in _IDS_POR_FAMILIA.items():
            if candidato in ids:
                return familia
    return FAMILIA_DESCONOCIDA


def _leer_texto(ruta: Path) -> str | None:
    """Lee un fichero de texto; None si no existe o no se puede leer."""
    try:
        return ruta.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _leer_os_release() -> str:
    """Contenido del primer os-release legible (`/etc` antes que `/usr/lib`); vacío si no hay."""
    for ruta in RUTAS_OS_RELEASE:
        texto = _leer_texto(ruta)
        if texto is not None:
            return texto
    return ""


def _es_root_linux() -> bool:
    """True si el proceso corre con UID efectivo 0."""
    geteuid = getattr(os, "geteuid", None)
    return geteuid is not None and geteuid() == 0


def _detectar_mac() -> str:
    """Módulo de control de acceso obligatorio activo, según ficheros de /sys (solo lectura)."""
    enforce = _leer_texto(RUTA_SELINUX)
    if enforce is not None and enforce.strip() in ("0", "1"):
        return MAC_SELINUX
    apparmor = _leer_texto(RUTA_APPARMOR)
    if apparmor is not None and apparmor.strip().upper().startswith("Y"):
        return MAC_APPARMOR
    return MAC_NINGUNO


def _detectar_linux() -> dict[str, Any]:
    """Campos de `Capacidades` propios de Linux."""
    os_release = parsear_os_release(_leer_os_release())
    identificador = os_release.get("ID", "").strip().lower()
    id_like = tuple(os_release.get("ID_LIKE", "").lower().split())
    return {
        "linux_id": identificador,
        "linux_id_like": id_like,
        "linux_version_id": os_release.get("VERSION_ID", "").strip(),
        "linux_nombre": os_release.get("NAME", "").strip(),
        "familia": familia_de_distribucion(identificador, id_like),
        "es_root": _es_root_linux(),
        "mac": _detectar_mac(),
    }


# --- Binarios ----------------------------------------------------------------------------
def resolver_binarios(nombres: Iterable[str], so: str) -> dict[str, str | None]:
    """Resuelve cada nombre a su ruta absoluta con `shutil.which`, o None si no está.

    En Linux se busca en el PATH fijo del ejecutor, no en el del proceso (regla 10).
    """
    path = PATH_LINUX_FIJO if so == SO_LINUX else None
    tipo_ruta = PurePosixPath if so == SO_LINUX else PureWindowsPath
    resueltos: dict[str, str | None] = {}
    for nombre in sorted(set(nombres)):
        ruta = shutil.which(nombre, path=path)
        resueltos[nombre] = ruta if ruta and tipo_ruta(ruta).is_absolute() else None
    return resueltos


def binarios_declarados(cat: catalogo.Catalogo) -> set[str]:
    """Nombres de binario que declara algún `requisitos.binarios` del catálogo."""
    return {binario for entrada in cat.entradas.values() for binario in entrada.requisitos.binarios}


# --- API pública -------------------------------------------------------------------------
def detectar_capacidades(binarios: Iterable[str] = ()) -> Capacidades:
    """Detecta las capacidades de este equipo; resuelve además los `binarios` indicados.

    No lanza excepciones por un entorno raro: un dato que no se puede leer queda en su valor
    neutro y el SO desconocido produce `so == "otro"`.
    """
    so = _sistema_operativo()
    campos: dict[str, Any] = {}
    if so == SO_WINDOWS:
        campos = _detectar_windows()
    elif so == SO_LINUX:
        campos = _detectar_linux()
    return Capacidades(so=so, binarios=resolver_binarios(binarios, so), **campos)


@lru_cache(maxsize=1)
def capacidades_del_equipo() -> Capacidades:
    """Capacidades de este equipo con los binarios declarados por el catálogo, calculadas una vez."""
    return detectar_capacidades(binarios_declarados(catalogo.cargar_catalogo()))
