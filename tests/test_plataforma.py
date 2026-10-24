"""Tests de src/plataforma: detección de capacidades de Windows y Linux, siempre simulada.

Ningún test lee el registro, `/etc/os-release` ni `/sys` reales: los lectores de bajo nivel se
parchean (el registro con un `winreg` falso, os-release con los ficheros de
`tests/fixtures/os-release/`). Tampoco se ejecuta ningún subproceso.
"""

from __future__ import annotations

import ast
import json
import os
import runpy
import sys
import types
from pathlib import Path

import pytest

from src import catalogo
from src.plataforma import deteccion
from src.plataforma.deteccion import Capacidades, detectar_capacidades, parsear_os_release

FIXTURES_OS_RELEASE = Path(__file__).parent / "fixtures" / "os-release"

# Los lectores reales, guardados antes de que la fixture autouse de conftest los sustituya.
LEER_REGISTRO_REAL = deteccion._leer_registro_windows
ES_ADMIN_REAL = deteccion._es_administrador_windows
ES_ROOT_REAL = deteccion._es_root_linux
SISTEMA_REAL = deteccion._sistema_operativo
MAC_REAL = deteccion._detectar_mac


def texto_os_release(nombre: str) -> str:
    return (FIXTURES_OS_RELEASE / nombre).read_text(encoding="utf-8")


def equipo_linux(monkeypatch: pytest.MonkeyPatch, fixture: str, *, root: bool = False, ficheros: dict | None = None) -> None:
    """Simula un Linux cuyo os-release es el fichero `fixture`."""
    monkeypatch.setattr(deteccion, "_sistema_operativo", lambda: "linux")
    monkeypatch.setattr(deteccion, "_leer_os_release", lambda: texto_os_release(fixture))
    monkeypatch.setattr(deteccion, "_es_root_linux", lambda: root)
    monkeypatch.setattr(deteccion, "_leer_texto", lambda ruta: (ficheros or {}).get(ruta))


def equipo_windows(
    monkeypatch: pytest.MonkeyPatch, *, build: str, edicion: str, ubr: int = 1, version: str = "", admin: bool = False
) -> None:
    """Simula un Windows con los valores de registro indicados."""
    registro = {"CurrentBuildNumber": build, "UBR": ubr, "EditionID": edicion, "DisplayVersion": version}
    monkeypatch.setattr(deteccion, "_sistema_operativo", lambda: "windows")
    monkeypatch.setattr(deteccion, "_leer_registro_windows", lambda: registro)
    monkeypatch.setattr(deteccion, "_es_administrador_windows", lambda: admin)


# --- Familias de Linux -------------------------------------------------------------------
@pytest.mark.parametrize(
    ("fixture", "familia", "identificador", "version_id", "nombre"),
    [
        ("ubuntu-24.04", "debian", "ubuntu", "24.04", "Ubuntu"),
        ("debian-12", "debian", "debian", "12", "Debian GNU/Linux"),
        ("kali-rolling", "debian", "kali", "2024.4", "Kali GNU/Linux"),
        ("linuxmint-22", "debian", "linuxmint", "22", "Linux Mint"),
        ("fedora-41", "rhel", "fedora", "41", "Fedora Linux"),
        ("rocky-9", "rhel", "rocky", "9.4", "Rocky Linux"),
        ("arch", "arch", "arch", "", "Arch Linux"),
        ("opensuse-tumbleweed", "suse", "opensuse-tumbleweed", "20250101", "openSUSE Tumbleweed"),
    ],
)
def test_familia_y_campos_de_cada_distribucion(monkeypatch, fixture, familia, identificador, version_id, nombre):
    equipo_linux(monkeypatch, fixture)

    caps = detectar_capacidades()

    assert caps.so == "linux"
    assert caps.familia == familia
    assert caps.linux_id == identificador
    assert caps.linux_version_id == version_id
    assert caps.linux_nombre == nombre


def test_solo_kali_es_kali(monkeypatch):
    equipo_linux(monkeypatch, "kali-rolling")
    assert detectar_capacidades().es_kali is True
    equipo_linux(monkeypatch, "debian-12")
    assert detectar_capacidades().es_kali is False


def test_id_like_se_conserva_como_tupla(monkeypatch):
    equipo_linux(monkeypatch, "linuxmint-22")
    assert detectar_capacidades().linux_id_like == ("ubuntu", "debian")


@pytest.mark.parametrize("fixture", ["malformado", "vacio"])
def test_os_release_malformado_o_vacio_da_familia_desconocida_sin_excepcion(monkeypatch, fixture):
    equipo_linux(monkeypatch, fixture)

    caps = detectar_capacidades()

    assert caps.so == "linux"
    assert caps.familia == "desconocida"
    assert caps.linux_id == ""
    assert caps.es_kali is False


def test_sin_fichero_os_release_la_familia_es_desconocida(monkeypatch):
    monkeypatch.setattr(deteccion, "_sistema_operativo", lambda: "linux")
    monkeypatch.setattr(deteccion, "_leer_texto", lambda ruta: None)  # ningún os-release legible
    monkeypatch.setattr(deteccion, "_es_root_linux", lambda: False)

    assert detectar_capacidades().familia == "desconocida"


def test_la_familia_se_deduce_de_id_like_si_el_id_no_se_conoce():
    assert deteccion.familia_de_distribucion("distro-rara", ["rhel", "fedora"]) == "rhel"
    assert deteccion.familia_de_distribucion("distro-rara", ["otra-cosa"]) == "desconocida"
    assert deteccion.familia_de_distribucion("OpenSUSE-Leap", []) == "suse"
    assert deteccion.familia_de_distribucion("sles", []) == "suse"
    assert deteccion.familia_de_distribucion("", []) == "desconocida"


def test_el_id_prevalece_sobre_id_like():
    assert deteccion.familia_de_distribucion("fedora", ["debian"]) == "rhel"


# --- Parser de os-release ----------------------------------------------------------------
def test_parser_gestiona_comillas_comentarios_y_escapes():
    texto = (
        "# comentario\n"
        "\n"
        'ID="ubuntu"\n'
        "NAME='Linux Mint'\n"
        'VERSION="a \\"b\\" c"\n'
        "SIN_COMILLAS=arch # nota final\n"
        "VACIO=\n"
        'CON_ALMOHADILLA=" # no es un comentario"\n'
        'CIERRE_Y_COMENTARIO="x" # nota\n'
    )

    campos = parsear_os_release(texto)

    assert campos["ID"] == "ubuntu"
    assert campos["NAME"] == "Linux Mint"
    assert campos["VERSION"] == 'a "b" c'
    assert campos["SIN_COMILLAS"] == "arch"
    assert campos["VACIO"] == ""
    assert campos["CON_ALMOHADILLA"] == " # no es un comentario"
    assert campos["CIERRE_Y_COMENTARIO"] == "x"


def test_parser_tolera_saltos_de_linea_de_windows():
    assert parsear_os_release('ID=debian\r\nNAME="Debian"\r\n') == {"ID": "debian", "NAME": "Debian"}


def test_parser_descarta_lineas_mal_formadas_pero_conserva_las_buenas():
    texto = 'basura sin igual\n=sin clave\n1MAL=x\nID="sin cerrar\nNAME=bien\nVERSION_ID="12" resto\n'
    assert parsear_os_release(texto) == {"NAME": "bien"}


def test_parser_no_lanza_con_bytes_raros_ni_con_texto_vacio():
    assert parsear_os_release("") == {}
    assert parsear_os_release("\x00\x01=\x02\n=\n==\n") == {}


# --- Windows -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("build", "edicion", "es_11"),
    [
        ("19045", "Core", False),  # Windows 10 Home
        ("19045", "Professional", False),  # Windows 10 Pro
        ("26100", "Core", True),  # Windows 11 Home
        ("26100", "Professional", True),  # Windows 11 Pro
        ("22000", "Professional", True),  # primer build de Windows 11
        ("21999", "Professional", False),
    ],
)
def test_windows_10_y_11_home_y_pro(monkeypatch, build, edicion, es_11):
    equipo_windows(monkeypatch, build=build, edicion=edicion, ubr=5555, version="24H2")

    caps = detectar_capacidades()

    assert caps.so == "windows"
    assert caps.windows_build == int(build)
    assert caps.windows_ubr == 5555
    assert caps.windows_edicion == edicion
    assert caps.windows_version == "24H2"
    assert caps.es_windows11 is es_11
    assert caps.es_kali is False


def test_es_admin_refleja_la_comprobacion_de_windows(monkeypatch):
    equipo_windows(monkeypatch, build="26100", edicion="Core", admin=True)
    assert detectar_capacidades().es_admin is True
    equipo_windows(monkeypatch, build="26100", edicion="Core", admin=False)
    assert detectar_capacidades().es_admin is False


def test_registro_ilegible_deja_los_campos_en_su_valor_neutro(monkeypatch):
    monkeypatch.setattr(deteccion, "_sistema_operativo", lambda: "windows")
    monkeypatch.setattr(deteccion, "_leer_registro_windows", lambda: {})
    monkeypatch.setattr(deteccion, "_es_administrador_windows", lambda: False)

    caps = detectar_capacidades()

    assert caps.so == "windows"
    assert caps.windows_build is None
    assert caps.windows_ubr is None
    assert caps.windows_edicion == ""
    assert caps.es_windows11 is False


def test_valores_de_registro_corruptos_no_lanzan_excepcion(monkeypatch):
    registro = {"CurrentBuildNumber": "no-numerico", "UBR": None, "EditionID": 7, "DisplayVersion": b"x"}
    monkeypatch.setattr(deteccion, "_sistema_operativo", lambda: "windows")
    monkeypatch.setattr(deteccion, "_leer_registro_windows", lambda: registro)
    monkeypatch.setattr(deteccion, "_es_administrador_windows", lambda: False)

    caps = detectar_capacidades()

    assert caps.windows_build is None
    assert caps.windows_ubr is None
    assert caps.windows_edicion == ""
    assert caps.windows_version == ""


def _winreg_falso(valores: dict, accesos: list) -> types.SimpleNamespace:
    class Clave:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def abrir(hive, ruta, reservado, acceso):
        accesos.append((hive, ruta, acceso))
        return Clave()

    def consultar(clave, nombre):
        if nombre not in valores:
            raise FileNotFoundError(nombre)
        return valores[nombre], 1

    return types.SimpleNamespace(
        HKEY_LOCAL_MACHINE="HKLM",
        KEY_READ=0x20019,
        KEY_WOW64_64KEY=0x100,
        OpenKey=abrir,
        QueryValueEx=consultar,
    )


def test_el_registro_se_abre_solo_en_modo_lectura_y_en_la_clave_prevista(monkeypatch):
    accesos: list = []
    valores = {"CurrentBuildNumber": "26100", "UBR": 1234, "EditionID": "Core"}  # sin DisplayVersion
    monkeypatch.setitem(sys.modules, "winreg", _winreg_falso(valores, accesos))

    leido = LEER_REGISTRO_REAL()

    assert leido == valores
    assert accesos == [("HKLM", r"SOFTWARE\Microsoft\Windows NT\CurrentVersion", 0x20019 | 0x100)]
    escritura = 0x2  # KEY_SET_VALUE
    assert accesos[0][2] & escritura == 0


def test_sin_winreg_o_sin_clave_el_lector_devuelve_vacio(monkeypatch):
    monkeypatch.setitem(sys.modules, "winreg", None)  # el import lanza ImportError
    assert LEER_REGISTRO_REAL() == {}

    falso = _winreg_falso({}, [])
    falso.OpenKey = lambda *_: (_ for _ in ()).throw(OSError("sin acceso"))
    monkeypatch.setitem(sys.modules, "winreg", falso)
    assert LEER_REGISTRO_REAL() == {}


def test_comprobacion_de_administrador_con_la_api_de_windows(monkeypatch):
    shell32 = types.SimpleNamespace(IsUserAnAdmin=lambda: 1)
    monkeypatch.setattr(deteccion, "ctypes", types.SimpleNamespace(windll=types.SimpleNamespace(shell32=shell32)))
    assert ES_ADMIN_REAL() is True

    shell32.IsUserAnAdmin = lambda: 0
    assert ES_ADMIN_REAL() is False


def test_sin_windll_no_es_administrador(monkeypatch):
    monkeypatch.setattr(deteccion, "ctypes", types.SimpleNamespace())  # sin atributo windll (p. ej. Linux)
    assert ES_ADMIN_REAL() is False


# --- Root, MAC y sistema -----------------------------------------------------------------
def test_es_root_segun_el_uid_efectivo(monkeypatch):
    monkeypatch.setattr(os, "geteuid", lambda: 0, raising=False)
    assert ES_ROOT_REAL() is True
    monkeypatch.setattr(os, "geteuid", lambda: 1000, raising=False)
    assert ES_ROOT_REAL() is False


def test_sin_geteuid_no_es_root(monkeypatch):
    monkeypatch.delattr(os, "geteuid", raising=False)
    assert ES_ROOT_REAL() is False


def test_es_root_se_propaga_a_las_capacidades(monkeypatch):
    equipo_linux(monkeypatch, "debian-12", root=True)
    caps = detectar_capacidades()
    assert caps.es_root is True
    assert caps.es_admin is False


@pytest.mark.parametrize(
    ("ficheros", "esperado"),
    [
        ({deteccion.RUTA_APPARMOR: "Y\n"}, "apparmor"),
        ({deteccion.RUTA_APPARMOR: "N\n"}, "ninguno"),
        ({deteccion.RUTA_SELINUX: "1"}, "selinux"),
        ({deteccion.RUTA_SELINUX: "0"}, "selinux"),  # permisivo: SELinux sigue activo
        ({deteccion.RUTA_SELINUX: "1", deteccion.RUTA_APPARMOR: "Y\n"}, "selinux"),
        ({deteccion.RUTA_SELINUX: "basura"}, "ninguno"),
        ({}, "ninguno"),
    ],
)
def test_deteccion_de_mac(monkeypatch, ficheros, esperado):
    monkeypatch.setattr(deteccion, "_leer_texto", lambda ruta: ficheros.get(ruta))
    assert MAC_REAL() == esperado


def test_mac_se_propaga_a_las_capacidades(monkeypatch):
    equipo_linux(monkeypatch, "ubuntu-24.04", ficheros={deteccion.RUTA_APPARMOR: "Y\n"})
    assert detectar_capacidades().mac == "apparmor"


def test_en_windows_no_se_consulta_la_mac(monkeypatch):
    equipo_windows(monkeypatch, build="26100", edicion="Core")
    assert detectar_capacidades().mac == "ninguno"


@pytest.mark.parametrize(
    ("plataforma", "so"),
    [("win32", "windows"), ("linux", "linux"), ("linux2", "linux"), ("darwin", "otro"), ("freebsd14", "otro")],
)
def test_clasificacion_del_sistema(monkeypatch, plataforma, so):
    monkeypatch.setattr(sys, "platform", plataforma)
    assert SISTEMA_REAL() == so


def test_so_otro_no_detecta_nada_mas(monkeypatch):
    monkeypatch.setattr(deteccion, "_sistema_operativo", lambda: "otro")
    caps = detectar_capacidades()
    assert caps == Capacidades(so="otro")


# --- Binarios ----------------------------------------------------------------------------
def test_binarios_se_resuelven_a_ruta_absoluta_o_none(monkeypatch):
    equipo_linux(monkeypatch, "debian-12")
    monkeypatch.setattr(deteccion.shutil, "which", lambda nombre, path=None: "/usr/sbin/ufw" if nombre == "ufw" else None)

    caps = detectar_capacidades(["ufw", "lynis"])

    assert caps.binarios == {"lynis": None, "ufw": "/usr/sbin/ufw"}


def test_en_linux_los_binarios_se_buscan_en_el_path_fijo(monkeypatch):
    equipo_linux(monkeypatch, "debian-12")
    caminos: list = []
    monkeypatch.setattr(deteccion.shutil, "which", lambda nombre, path=None: caminos.append(path))

    detectar_capacidades(["ufw"])

    assert caminos == [deteccion.PATH_LINUX_FIJO]


def test_en_windows_los_binarios_usan_el_path_del_proceso(monkeypatch):
    caminos: list = []
    monkeypatch.setattr(deteccion.shutil, "which", lambda nombre, path=None: caminos.append(path))

    detectar_capacidades(["herramienta"])

    assert caminos == [None]


def test_una_ruta_relativa_no_cuenta_como_binario_encontrado(monkeypatch):
    equipo_linux(monkeypatch, "debian-12")
    monkeypatch.setattr(deteccion.shutil, "which", lambda nombre, path=None: "bin/ufw")

    assert detectar_capacidades(["ufw"]).binarios == {"ufw": None}


def test_los_binarios_declarados_salen_del_catalogo(tmp_path):
    (tmp_path / "herramientas_llm.yaml").write_text("version: 1\nentradas: []\n", encoding="utf-8")
    linux = tmp_path / "linux"
    linux.mkdir()
    (linux / "lnx_demo.yaml").write_text(
        "version: 1\n"
        "entradas:\n"
        "  - id: lnx_demo\n"
        "    titulo: Demo\n"
        "    descripcion_llm: Demo.\n"
        "    justificacion: Demo.\n"
        "    tipo: comprobacion\n"
        "    nivel: lectura\n"
        "    riesgo: bajo\n"
        "    sensibilidad: tecnica\n"
        "    perfiles: [hogar]\n"
        "    plataforma: {so: linux}\n"
        "    requisitos: {privilegios: usuario, binarios: [ufw, iptables]}\n"
        "    motor: comando\n"
        "    argv: [ufw, status]\n"
        "    area: red\n"
        "    severidad: media\n"
        "    peso: 5\n",
        encoding="utf-8",
    )

    assert deteccion.binarios_declarados(catalogo.cargar_catalogo(tmp_path)) == {"ufw", "iptables"}
    assert deteccion.binarios_declarados(catalogo.cargar_catalogo()) == set()  # el catálogo real no declara ninguno


# --- Sin subprocess ----------------------------------------------------------------------
def test_la_deteccion_no_importa_subprocess_ni_os_system():
    codigo = Path(deteccion.__file__).read_text(encoding="utf-8")
    arbol = ast.parse(codigo)
    importados = {
        alias.name.split(".")[0]
        for nodo in ast.walk(arbol)
        if isinstance(nodo, (ast.Import, ast.ImportFrom))
        for alias in (nodo.names if isinstance(nodo, ast.Import) else [ast.alias(name=nodo.module or "")])
    }
    assert "subprocess" not in importados
    assert "os.system" not in codigo and "os.popen" not in codigo


# --- Diagnóstico JSON --------------------------------------------------------------------
def test_a_dict_es_serializable_y_no_revela_usuario_ni_equipo(monkeypatch):
    import getpass
    import socket

    # Usuario y equipo ficticios y únicos: con los reales el test dependería de la máquina
    # (un equipo llamado «windows11» coincide con la clave legítima «es_windows11»).
    usuario, equipo = "usuario_secreto_xyz", "equipo_secreto_xyz"
    monkeypatch.setattr(getpass, "getuser", lambda: usuario)
    monkeypatch.setattr(socket, "gethostname", lambda: equipo)
    monkeypatch.setattr(Path, "home", lambda: Path("C:/Users") / usuario)

    equipo_windows(monkeypatch, build="26100", edicion="Core", version="24H2")
    ruta_personal = str(Path.home() / "herramientas" / "tool.exe")
    monkeypatch.setattr(deteccion.shutil, "which", lambda nombre, path=None: ruta_personal)

    texto = json.dumps(detectar_capacidades(["tool"]).a_dict())

    assert usuario not in texto.lower()
    assert equipo not in texto.lower()
    assert json.loads(texto)["binarios"]["tool"].startswith("~")


def test_las_rutas_fuera_del_directorio_personal_no_se_tocan():
    assert deteccion._anonimizar_ruta("/usr/bin/ufw") == "/usr/bin/ufw"
    assert deteccion._anonimizar_ruta(None) is None


def test_python_m_src_plataforma_imprime_json_de_las_capacidades(capsys):
    runpy.run_module("src.plataforma", run_name="__main__")

    datos = json.loads(capsys.readouterr().out)

    assert datos["so"] == "windows"  # equipo simulado por conftest
    assert datos["windows_build"] == 26100
    assert datos["es_windows11"] is True
    assert set(datos) >= {"familia", "es_root", "es_admin", "mac", "binarios", "es_kali"}
    assert "hostname" not in datos and "usuario" not in datos


def test_capacidades_del_equipo_se_calcula_una_sola_vez(monkeypatch):
    llamadas: list = []
    original = deteccion.detectar_capacidades
    monkeypatch.setattr(deteccion, "detectar_capacidades", lambda binarios=(): llamadas.append(1) or original(binarios))
    deteccion.capacidades_del_equipo.cache_clear()

    primera = deteccion.capacidades_del_equipo()
    segunda = deteccion.capacidades_del_equipo()

    assert primera is segunda
    assert len(llamadas) == 1
