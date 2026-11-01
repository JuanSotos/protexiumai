"""Tests de src/politica.py: la política que se vuelve a comprobar en cada llamada (F05).

Las entradas sintéticas se derivan de entradas reales con `dataclasses.replace`, simulando un
catálogo alterado en memoria después de cargarlo. Ningún test ejecuta nada: la política es pura.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from src import catalogo, politica
from src.adaptadores import comando, powershell, registro
from src.adaptadores.base import Invocacion
from src.catalogo import ClaveRegistro, Plataforma, Requisitos
from src.plataforma.deteccion import Capacidades

WIN11_PRO = Capacidades(so="windows", windows_build=26100, windows_edicion="Professional")
UBUNTU = Capacidades(so="linux", linux_id="ubuntu", familia="debian")

CATALOGO = catalogo.cargar_catalogo()


def _entrada(tool_id: str = "get_defender_status") -> catalogo.Entrada:
    return CATALOGO.entradas[tool_id]


def _entrada_linux(argv: tuple[str, ...] = ("uname", "-r"), **cambios: object) -> catalogo.Entrada:
    valores: dict[str, object] = {
        "id": "lnx_sintetica",
        "plataforma": Plataforma(so="linux"),
        "requisitos": Requisitos(privilegios="usuario"),
        "motor": "comando",
        "plantilla": None,
        "argv": argv,
    }
    return replace(_entrada(), **{**valores, **cambios})  # type: ignore[arg-type]


def _entrada_registro(hive: str = "HKLM") -> catalogo.Entrada:
    return replace(
        _entrada(),
        id="win_registro_sintetica",
        motor="registro",
        plantilla=None,
        clave_registro=ClaveRegistro(hive=hive, ruta=r"SOFTWARE\Demo", valor="Valor"),
    )


# --- Decision ----------------------------------------------------------------------------
def test_la_decision_permitida_no_tiene_motivo():
    assert politica.PERMITIDA.permitida is True
    assert politica.PERMITIDA.motivo is None


@pytest.mark.parametrize("resultado, estado", [("rechazada", "error"), ("no_aplicable", "no_aplicable")])
def test_el_estado_de_una_decision_negativa(resultado, estado):
    decision = politica.Decision(resultado, "x", "y")
    assert decision.permitida is False
    assert decision.estado == estado


# --- evaluar_llamada ---------------------------------------------------------------------
def test_una_llamada_valida_se_permite():
    assert politica.evaluar_llamada("get_defender_status", _entrada(), {}, WIN11_PRO, "hogar").permitida


def test_id_desconocido_se_rechaza_con_el_mensaje_de_siempre():
    decision = politica.evaluar_llamada("borrar_disco", None, {}, WIN11_PRO, "hogar")
    assert decision.resultado == "rechazada"
    assert decision.motivo == "tool_id_desconocido"
    assert decision.mensaje == "Herramienta desconocida: 'borrar_disco'."


def test_motor_python_se_rechaza_con_motivo_propio():
    entrada = replace(_entrada(), motor="python", plantilla=None)
    decision = politica.evaluar_llamada(entrada.id, entrada, {}, WIN11_PRO, "hogar")
    assert decision.motivo == "motor_reservado"


def test_motor_desconocido_se_rechaza():
    entrada = replace(_entrada(), motor="bash")
    assert politica.evaluar_llamada(entrada.id, entrada, {}, WIN11_PRO, "hogar").motivo == "motor_no_soportado"


@pytest.mark.parametrize("motor", ["powershell", "registro"])
def test_motor_de_windows_en_una_entrada_de_linux_es_incoherente(motor):
    entrada = replace(_entrada(), motor=motor, plataforma=Plataforma(so="linux"), requisitos=Requisitos("usuario"))
    decision = politica.evaluar_llamada(entrada.id, entrada, {}, UBUNTU, "hogar")
    assert decision.resultado == "rechazada"
    assert decision.motivo == "motor_no_soportado"


def test_comando_en_una_entrada_de_windows_no_se_admite_en_h1():
    entrada = replace(_entrada(), motor="comando", plantilla=None, argv=("netsh",))
    assert politica.evaluar_llamada(entrada.id, entrada, {}, WIN11_PRO, "hogar").motivo == "motor_no_soportado"


def test_el_motor_se_comprueba_antes_que_la_aplicabilidad():
    entrada = replace(_entrada(), motor="python", plantilla=None)
    assert politica.evaluar_llamada(entrada.id, entrada, {}, UBUNTU, "hogar").motivo == "motor_reservado"


@pytest.mark.parametrize(
    "entrada, capacidades, perfil, fragmento",
    [
        (_entrada(), UBUNTU, "hogar", "windows"),
        (replace(_entrada(), plataforma=Plataforma(so="windows", build_min=30000)), WIN11_PRO, "hogar", "build"),
        (replace(_entrada(), plataforma=Plataforma(so="windows", ediciones=("Enterprise",))), WIN11_PRO, "hogar", "edición"),
        (replace(_entrada(), perfiles=("sistemas",)), WIN11_PRO, "hogar", "perfil"),
        (_entrada_linux(requisitos=Requisitos("usuario", binarios=("sshd",))), UBUNTU, "hogar", "sshd"),
    ],
)
def test_una_entrada_no_aplicable_devuelve_no_aplicable_y_no_un_error(entrada, capacidades, perfil, fragmento):
    decision = politica.evaluar_llamada(entrada.id, entrada, {}, capacidades, perfil)
    assert decision.resultado == "no_aplicable"
    assert decision.motivo == "no_aplicable"
    assert decision.estado == "no_aplicable"
    assert fragmento in decision.mensaje


def test_parametro_no_declarado_conserva_motivo_y_mensaje():
    decision = politica.evaluar_llamada("start_quick_scan", _entrada("start_quick_scan"), {"foo": "bar"}, WIN11_PRO, "hogar")
    assert decision.motivo == "parametro_no_declarado"
    assert decision.mensaje == "Parámetro(s) no declarado(s) para 'start_quick_scan': ['foo']."


def test_parametro_faltante_conserva_motivo_y_mensaje():
    entrada = _entrada("set_firewall_profile")
    decision = politica.evaluar_llamada(entrada.id, entrada, {"profile": "Private"}, WIN11_PRO, "hogar")
    assert decision.motivo == "parametro_faltante"
    assert decision.mensaje == "Falta(n) parámetro(s) obligatorio(s) para 'set_firewall_profile': ['enabled']."


def test_valor_fuera_de_enum_conserva_motivo_y_mensaje():
    entrada = _entrada("set_firewall_profile")
    decision = politica.evaluar_llamada(entrada.id, entrada, {"profile": "Evil", "enabled": "True"}, WIN11_PRO, "hogar")
    assert decision.motivo == "valor_fuera_de_enum"
    assert decision.mensaje == (
        "Valor 'Evil' no permitido para 'profile' (permitidos: ['Domain', 'Private', 'Public'])."
    )


# --- evaluar_invocacion ------------------------------------------------------------------
def test_una_invocacion_de_powershell_del_catalogo_se_permite():
    invocacion = powershell.construir(_entrada(), {})
    assert politica.evaluar_invocacion(invocacion).permitida


@pytest.mark.parametrize("anadido", ["; IEX $x", "; Invoke-Expression $x", "; Start-Process calc", "; cmd /c dir"])
def test_un_token_denegado_en_el_texto_de_powershell_se_rechaza(anadido):
    entrada = replace(_entrada(), plantilla=_entrada().plantilla + anadido)
    decision = politica.evaluar_invocacion(powershell.construir(entrada, {}))
    assert decision.resultado == "rechazada"
    assert decision.motivo == "denegado_por_politica"


def test_una_invocacion_de_comando_limpia_se_permite():
    assert politica.evaluar_invocacion(comando.construir(_entrada_linux(), {})).permitida


@pytest.mark.parametrize(
    "argv",
    [("sudo", "ls"), ("su", "-"), ("pkexec", "id"), ("doas", "id"), ("/usr/bin/sudo", "ls"), ("env", "sudo", "id"), ("SUDO",)],
)
def test_los_binarios_de_elevacion_se_rechazan_en_cualquier_posicion(argv):
    decision = politica.evaluar_invocacion(comando.construir(_entrada_linux(argv=argv), {}))
    assert decision.motivo == "denegado_por_politica"
    assert "elevación" in decision.mensaje


@pytest.mark.parametrize("argv", [("rm", "-rf", "/"), ("bash", "-c", "id"), ("wevtutil", "cl", "System")])
def test_un_token_denegado_repartido_entre_elementos_de_argv_se_rechaza(argv):
    decision = politica.evaluar_invocacion(comando.construir(_entrada_linux(argv=argv), {}))
    assert decision.motivo == "denegado_por_politica"
    assert "token denegado" in decision.mensaje


def test_un_token_denegado_dentro_de_un_elemento_de_argv_se_rechaza():
    decision = politica.evaluar_invocacion(comando.construir(_entrada_linux(argv=("python3", "IEX")), {}))
    assert decision.motivo == "denegado_por_politica"


def test_suma_no_casa_con_su():
    assert politica.evaluar_invocacion(comando.construir(_entrada_linux(argv=("suma", "--version")), {})).permitida


def test_una_lectura_de_registro_valida_se_permite():
    assert politica.evaluar_invocacion(registro.construir(_entrada_registro(), {})).permitida


def test_un_hive_desconocido_no_llega_a_ejecutarse():
    decision = politica.evaluar_invocacion(registro.construir(_entrada_registro(hive="HKEY_EVIL"), {}))
    assert decision.resultado == "rechazada"
    assert decision.motivo == "hive_desconocido"


def test_una_invocacion_de_registro_sin_clave_se_rechaza():
    invocacion = Invocacion(tool_id="x", motor="registro", texto="", timeout_s=1, clave=None)
    assert politica.evaluar_invocacion(invocacion).motivo == "hive_desconocido"


def test_un_token_denegado_en_la_ruta_de_registro_se_rechaza():
    entrada = replace(_entrada_registro(), clave_registro=ClaveRegistro("HKLM", r"SOFTWARE\HailMary", "x"))
    assert politica.evaluar_invocacion(registro.construir(entrada, {})).motivo == "denegado_por_politica"
