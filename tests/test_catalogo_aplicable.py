"""Tests de `catalogo.aplicable`: qué entradas del catálogo aplican a cada equipo y perfil.

Las entradas sintéticas se derivan de una entrada real con `dataclasses.replace`; ningún test
ejecuta comandos. Las capacidades se construyen a mano (o desde YAML temporales).
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from src import catalogo
from src.catalogo import Entrada, Plataforma, Requisitos, aplicable
from src.plataforma.deteccion import Capacidades

WIN10_HOME = Capacidades(so="windows", windows_build=19045, windows_edicion="Core")
WIN10_PRO = Capacidades(so="windows", windows_build=19045, windows_edicion="Professional")
WIN11_HOME = Capacidades(so="windows", windows_build=26100, windows_edicion="Core")
WIN11_PRO = Capacidades(so="windows", windows_build=26100, windows_edicion="Professional")
UBUNTU = Capacidades(so="linux", linux_id="ubuntu", familia="debian")
FEDORA = Capacidades(so="linux", linux_id="fedora", familia="rhel")
DESCONOCIDA = Capacidades(so="linux", familia="desconocida")


def entrada_windows(**plataforma: object) -> Entrada:
    """Entrada de Windows sintética; `plataforma` ajusta build_min, build_max o ediciones."""
    base = catalogo.cargar_catalogo().entradas["get_defender_status"]
    return replace(base, plataforma=Plataforma(so="windows", **plataforma))  # type: ignore[arg-type]


def entrada_linux(*, familias: tuple[str, ...] | None = None, binarios: tuple[str, ...] = (), privilegios: str = "usuario") -> Entrada:
    """Entrada de Linux sintética con motor `comando`."""
    base = catalogo.cargar_catalogo().entradas["get_defender_status"]
    return replace(
        base,
        id="lnx_sintetica",
        plataforma=Plataforma(so="linux", familias=familias),
        requisitos=Requisitos(privilegios=privilegios, binarios=binarios),
        motor="comando",
        plantilla=None,
        argv=("uname",),
    )


# --- Sistema operativo -------------------------------------------------------------------
@pytest.mark.parametrize("caps", [WIN10_HOME, WIN10_PRO, WIN11_HOME, WIN11_PRO])
def test_una_entrada_de_windows_aplica_a_cualquier_windows(caps):
    assert aplicable(entrada_windows(), caps, "hogar") == (True, "aplicable")


@pytest.mark.parametrize("caps", [UBUNTU, Capacidades(so="otro")])
def test_una_entrada_de_windows_no_aplica_fuera_de_windows(caps):
    aplica, motivo = aplicable(entrada_windows(), caps, "hogar")
    assert aplica is False
    assert "windows" in motivo


def test_una_entrada_de_linux_no_aplica_en_windows():
    aplica, motivo = aplicable(entrada_linux(), WIN11_PRO, "hogar")
    assert aplica is False
    assert "linux" in motivo


# --- Build y edición de Windows ----------------------------------------------------------
def test_entrada_solo_para_windows_11_no_aplica_en_windows_10():
    entrada = entrada_windows(build_min=22000)

    assert aplicable(entrada, WIN10_HOME, "hogar")[0] is False
    assert aplicable(entrada, WIN10_PRO, "hogar")[0] is False
    assert aplicable(entrada, WIN11_HOME, "hogar")[0] is True
    assert aplicable(entrada, WIN11_PRO, "hogar")[0] is True


def test_el_motivo_de_build_indica_el_build_exigido_y_el_del_equipo():
    _, motivo = aplicable(entrada_windows(build_min=22000), WIN10_HOME, "hogar")
    assert "22000" in motivo and "19045" in motivo


def test_build_max_excluye_los_builds_posteriores():
    entrada = entrada_windows(build_max=19045)

    assert aplicable(entrada, WIN10_HOME, "hogar")[0] is True
    assert aplicable(entrada, WIN11_HOME, "hogar")[0] is False


def test_los_limites_de_build_son_inclusivos():
    entrada = entrada_windows(build_min=22000, build_max=22000)
    assert aplicable(entrada, Capacidades(so="windows", windows_build=22000), "hogar")[0] is True
    assert aplicable(entrada, Capacidades(so="windows", windows_build=21999), "hogar")[0] is False
    assert aplicable(entrada, Capacidades(so="windows", windows_build=22001), "hogar")[0] is False


def test_sin_build_conocido_una_entrada_con_limites_no_aplica_pero_sin_limites_si():
    sin_build = Capacidades(so="windows")

    assert aplicable(entrada_windows(build_min=22000), sin_build, "hogar")[0] is False
    assert aplicable(entrada_windows(), sin_build, "hogar")[0] is True


def test_ediciones_filtra_home_y_pro():
    solo_pro = entrada_windows(ediciones=("Professional", "Enterprise"))

    assert aplicable(solo_pro, WIN11_PRO, "hogar")[0] is True
    aplica, motivo = aplicable(solo_pro, WIN11_HOME, "hogar")
    assert aplica is False
    assert "Core" in motivo


def test_la_edicion_se_compara_sin_distinguir_mayusculas():
    assert aplicable(entrada_windows(ediciones=("professional",)), WIN11_PRO, "hogar")[0] is True


# --- Familia de Linux --------------------------------------------------------------------
def test_la_familia_filtra_las_entradas_de_linux():
    entrada = entrada_linux(familias=("debian",))

    assert aplicable(entrada, UBUNTU, "hogar")[0] is True
    aplica, motivo = aplicable(entrada, FEDORA, "hogar")
    assert aplica is False
    assert "rhel" in motivo


def test_familias_none_significa_todas_incluida_la_desconocida():
    assert aplicable(entrada_linux(), UBUNTU, "hogar")[0] is True
    assert aplicable(entrada_linux(), DESCONOCIDA, "hogar")[0] is True


def test_familia_desconocida_no_aplica_a_una_entrada_con_familias():
    assert aplicable(entrada_linux(familias=("debian", "rhel")), DESCONOCIDA, "hogar")[0] is False


# --- Binarios ----------------------------------------------------------------------------
def test_entrada_con_binario_ausente_no_aplica():
    entrada = entrada_linux(binarios=("ufw",))
    caps = Capacidades(so="linux", familia="debian", binarios={"ufw": None})

    aplica, motivo = aplicable(entrada, caps, "hogar")

    assert aplica is False
    assert "ufw" in motivo


def test_binario_no_detectado_cuenta_como_ausente():
    assert aplicable(entrada_linux(binarios=("ufw",)), UBUNTU, "hogar")[0] is False


def test_entrada_con_todos_sus_binarios_aplica():
    entrada = entrada_linux(binarios=("ufw", "iptables"))
    caps = Capacidades(so="linux", familia="debian", binarios={"ufw": "/usr/sbin/ufw", "iptables": "/usr/sbin/iptables"})
    assert aplicable(entrada, caps, "hogar")[0] is True


def test_un_solo_binario_ausente_basta_para_excluir():
    entrada = entrada_linux(binarios=("ufw", "iptables"))
    caps = Capacidades(so="linux", familia="debian", binarios={"ufw": "/usr/sbin/ufw", "iptables": None})
    assert aplicable(entrada, caps, "hogar") == (False, "falta el binario 'iptables'")


# --- Perfil y privilegios ----------------------------------------------------------------
def test_perfil_distinto_excluye_la_entrada():
    solo_sistemas = replace(entrada_windows(), perfiles=("sistemas",))

    assert aplicable(solo_sistemas, WIN11_PRO, "sistemas")[0] is True
    aplica, motivo = aplicable(solo_sistemas, WIN11_PRO, "hogar")
    assert aplica is False
    assert "hogar" in motivo


def test_un_perfil_inexistente_es_un_error():
    with pytest.raises(ValueError, match="perfil desconocido"):
        aplicable(entrada_windows(), WIN11_PRO, "invitado")


def test_los_privilegios_no_excluyen_una_entrada():
    exige_root = entrada_linux(privilegios="root")
    exige_admin = replace(entrada_windows(), requisitos=Requisitos(privilegios="admin"))

    assert UBUNTU.es_root is False and WIN11_PRO.es_admin is False
    assert aplicable(exige_root, UBUNTU, "hogar")[0] is True
    assert aplicable(exige_admin, WIN11_PRO, "hogar")[0] is True


# --- Con YAML real -----------------------------------------------------------------------
def test_aplicabilidad_sobre_entradas_cargadas_desde_yaml(tmp_path):
    (tmp_path / "herramientas_llm.yaml").write_text("version: 1\nentradas: []\n", encoding="utf-8")
    (tmp_path / "windows").mkdir()
    (tmp_path / "windows" / "win_solo_11.yaml").write_text(
        "version: 1\n"
        "entradas:\n"
        "  - id: win_solo_11\n"
        "    titulo: Solo Windows 11\n"
        "    descripcion_llm: Demo.\n"
        "    justificacion: Demo.\n"
        "    tipo: comprobacion\n"
        "    nivel: lectura\n"
        "    riesgo: bajo\n"
        "    sensibilidad: tecnica\n"
        "    perfiles: [hogar, sistemas]\n"
        "    plataforma: {so: windows, build_min: 22000, ediciones: [Professional]}\n"
        "    requisitos: {privilegios: admin}\n"
        "    motor: powershell\n"
        "    plantilla: Get-Date | ConvertTo-Json\n"
        "    area: sistema\n"
        "    severidad: baja\n"
        "    peso: 1\n",
        encoding="utf-8",
    )
    entrada = catalogo.cargar_catalogo(tmp_path).entradas["win_solo_11"]

    assert aplicable(entrada, WIN11_PRO, "hogar")[0] is True
    assert aplicable(entrada, WIN11_HOME, "hogar")[0] is False  # edición
    assert aplicable(entrada, WIN10_PRO, "hogar")[0] is False  # build
    assert aplicable(entrada, UBUNTU, "hogar")[0] is False  # sistema
