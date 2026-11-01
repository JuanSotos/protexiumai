"""Tests del adaptador `comando` (regla 10). subprocess.run y shutil.which están siempre mockeados."""

from __future__ import annotations

import subprocess
from dataclasses import replace
from unittest.mock import Mock, patch

import pytest

from src import catalogo
from src.adaptadores import comando
from src.catalogo import Plataforma, Requisitos

RUTA_UNAME = "/usr/bin/uname"


def _entrada(argv: tuple[str, ...] = ("uname", "-r"), parametros: dict[str, tuple[str, ...]] | None = None) -> catalogo.Entrada:
    base = catalogo.cargar_catalogo().entradas["get_defender_status"]
    return replace(
        base,
        id="lnx_demo",
        plataforma=Plataforma(so="linux"),
        requisitos=Requisitos(privilegios="usuario"),
        motor="comando",
        plantilla=None,
        argv=argv,
        parametros=parametros or {},
        timeout_s=7,
    )


def _proceso(stdout: str = "6.8.0\n", returncode: int = 0, stderr: str = "") -> Mock:
    return Mock(returncode=returncode, stdout=stdout, stderr=stderr)


def test_el_entorno_es_minimo_y_fijo():
    assert comando.ENTORNO_FIJO == {"LC_ALL": "C", "PATH": comando.PATH_FIJO}
    assert comando.PATH_FIJO == "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"


def test_construir_sustituye_cada_elemento_por_separado():
    entrada = _entrada(("ss", "-{familia}", "--{modo}"), {"familia": ("4", "6"), "modo": ("tcp", "udp")})
    invocacion = comando.construir(entrada, {"familia": "6", "modo": "udp"})
    assert invocacion.argv == ("ss", "-6", "--udp")
    assert invocacion.texto == "ss -6 --udp"


def test_un_valor_nunca_se_mezcla_con_otro_elemento_de_argv():
    entrada = _entrada(("grep", "{patron}", "/etc/ssh/sshd_config"), {"patron": ("a.b", "PermitRootLogin")})
    invocacion = comando.construir(entrada, {"patron": "a.b"})
    assert invocacion.argv == ("grep", "a.b", "/etc/ssh/sshd_config")
    assert len(invocacion.argv) == len(entrada.argv)


def test_sin_parametros_argv_se_usa_tal_cual():
    entrada = _entrada(("echo", "{literal}"))
    assert comando.construir(entrada, {}).argv == ("echo", "{literal}")


def test_ejecuta_con_ruta_absoluta_shell_false_entorno_fijo_y_timeout():
    invocacion = comando.construir(_entrada(), {})
    with patch("src.adaptadores.comando.shutil.which", return_value=RUTA_UNAME) as mock_which, \
         patch("src.adaptadores.comando.subprocess.run", return_value=_proceso()) as mock_run:
        salida = comando.ejecutar(invocacion)

    mock_which.assert_called_once_with("uname", path=comando.PATH_FIJO)
    assert mock_run.call_args.args[0] == [RUTA_UNAME, "-r"]
    argumentos = mock_run.call_args.kwargs
    assert argumentos["shell"] is False
    assert argumentos["env"] == comando.ENTORNO_FIJO
    assert argumentos["timeout"] == 7
    assert salida.estado == "ok"
    assert salida.datos == "6.8.0"


def test_el_argv_se_pasa_como_lista_nunca_como_cadena():
    invocacion = comando.construir(_entrada(("uname", "-r", "-s")), {})
    with patch("src.adaptadores.comando.shutil.which", return_value=RUTA_UNAME), \
         patch("src.adaptadores.comando.subprocess.run", return_value=_proceso()) as mock_run:
        comando.ejecutar(invocacion)
    assert isinstance(mock_run.call_args.args[0], list)


@pytest.mark.parametrize("resuelto", [None, "uname", "bin/uname"])
def test_binario_ausente_o_ruta_no_absoluta_es_no_aplicable(resuelto):
    with patch("src.adaptadores.comando.shutil.which", return_value=resuelto), \
         patch("src.adaptadores.comando.subprocess.run") as mock_run:
        salida = comando.ejecutar(comando.construir(_entrada(), {}))
    assert salida.estado == "no_aplicable"
    assert "uname" in salida.error
    mock_run.assert_not_called()


def test_binario_que_desaparece_al_lanzarlo_es_no_aplicable():
    with patch("src.adaptadores.comando.shutil.which", return_value=RUTA_UNAME), \
         patch("src.adaptadores.comando.subprocess.run", side_effect=FileNotFoundError()):
        salida = comando.ejecutar(comando.construir(_entrada(), {}))
    assert salida.estado == "no_aplicable"


def test_timeout_es_error():
    with patch("src.adaptadores.comando.shutil.which", return_value=RUTA_UNAME), \
         patch("src.adaptadores.comando.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="uname", timeout=7)):
        salida = comando.ejecutar(comando.construir(_entrada(), {}))
    assert salida.estado == "error"
    assert "7 segundos" in salida.error


@pytest.mark.parametrize("stderr, esperado", [("permiso denegado", "permiso denegado"), ("", "sin detalles")])
def test_codigo_de_salida_distinto_de_cero_es_error(stderr, esperado):
    with patch("src.adaptadores.comando.shutil.which", return_value=RUTA_UNAME), \
         patch("src.adaptadores.comando.subprocess.run", return_value=_proceso("", 2, stderr)):
        salida = comando.ejecutar(comando.construir(_entrada(), {}))
    assert salida.estado == "error"
    assert "código 2" in salida.error
    assert esperado in salida.error


def test_invocacion_sin_argv_es_error():
    salida = comando.ejecutar(replace(comando.construir(_entrada(), {}), argv=()))
    assert salida.estado == "error"
