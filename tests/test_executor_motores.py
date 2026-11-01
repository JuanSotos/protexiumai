"""Integración de src/executor.py con la política y los tres adaptadores (P11, F05).

Las herramientas `registro` y `comando` se prueban con catálogos YAML temporales: el catálogo
real no se toca. subprocess.run, shutil.which y winreg están siempre mockeados; ningún test
ejecuta nada sobre el sistema.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src import catalogo, executor
from src.adaptadores import comando, powershell, registro
from src.catalogo import ClaveRegistro, Plataforma
from src.plataforma.deteccion import Capacidades
from tests.test_adaptador_registro import WinregFalso

FIXTURES = Path(__file__).parent / "fixtures"
UBUNTU = Capacidades(so="linux", linux_id="ubuntu", familia="debian")

CABECERA_ENTRADA = """\
  - id: {id}
    titulo: Demo
    descripcion_llm: Demo.
    justificacion: Demo.
    tipo: herramienta
    nivel: lectura
    riesgo: bajo
    sensibilidad: tecnica
    area: sistema
"""

ENTRADA_REGISTRO = CABECERA_ENTRADA.format(id="win_reg_demo") + """\
    perfiles: [hogar]
    plataforma: {so: windows}
    requisitos: {privilegios: usuario}
    motor: registro
    clave_registro: {hive: HKLM, ruta: 'SOFTWARE\\Policies\\Demo', valor: Valor}
"""

ENTRADA_COMANDO = CABECERA_ENTRADA.format(id="lnx_demo") + """\
    perfiles: [hogar]
    plataforma: {so: linux}
    requisitos: {privilegios: usuario}
    motor: comando
    argv: [ss, "-{familia}", "-tln"]
    parametros: {familia: ["4", "6"]}
"""

ENTRADA_ROOT = CABECERA_ENTRADA.format(id="lnx_root") + """\
    perfiles: [hogar]
    plataforma: {so: linux}
    requisitos: {privilegios: root}
    motor: comando
    argv: [sshd, -T]
"""

ENTRADA_PYTHON = CABECERA_ENTRADA.format(id="py_demo") + """\
    perfiles: [hogar]
    plataforma: {so: windows}
    requisitos: {privilegios: usuario}
    motor: python
"""

ENTRADA_SISTEMAS = CABECERA_ENTRADA.format(id="win_sistemas") + """\
    perfiles: [sistemas]
    plataforma: {so: windows}
    requisitos: {privilegios: usuario}
    motor: powershell
    plantilla: Get-Date | ConvertTo-Json
"""

ENTRADA_SUDO = CABECERA_ENTRADA.format(id="lnx_sudo") + """\
    perfiles: [hogar]
    plataforma: {so: linux}
    requisitos: {privilegios: usuario}
    motor: comando
    argv: [sudo, id]
"""


def _proceso(stdout: str = "{}", returncode: int = 0) -> Mock:
    return Mock(returncode=returncode, stdout=stdout, stderr="")


def _catalogo_temporal(tmp_path: Path, *entradas: str) -> catalogo.Catalogo:
    (tmp_path / "herramientas_llm.yaml").write_text("version: 1\nentradas:\n" + "".join(entradas), encoding="utf-8")
    return catalogo.cargar_catalogo(tmp_path)


@pytest.fixture
def usar_catalogo(tmp_path, monkeypatch):
    """Sustituye el catálogo del executor por uno temporal con las entradas indicadas."""

    def _usar(*entradas: str) -> catalogo.Catalogo:
        raiz = tmp_path / "catalogo"
        raiz.mkdir()
        cat = _catalogo_temporal(raiz, *entradas)
        monkeypatch.setattr(executor, "CATALOGO", cat)
        return cat

    return _usar


@pytest.fixture
def espias(monkeypatch):
    """Envuelve el `ejecutar` de los tres adaptadores para saber por cuál pasa cada llamada."""
    espias_por_motor = {}
    for modulo in (powershell, registro, comando):
        espia = Mock(wraps=modulo.ejecutar)
        monkeypatch.setattr(modulo, "ejecutar", espia)
        espias_por_motor[modulo.MOTOR] = espia
    return espias_por_motor


def _leer_lineas_audit(ruta) -> list[dict]:
    if not ruta.exists():
        return []
    return [json.loads(linea) for linea in ruta.read_text(encoding="utf-8").splitlines() if linea.strip()]


# --- WHITELIST con los nuevos motores ----------------------------------------------------
def test_construir_whitelist_acepta_registro_y_comando(tmp_path):
    whitelist = executor.construir_whitelist(_catalogo_temporal(tmp_path, ENTRADA_REGISTRO, ENTRADA_COMANDO))
    assert whitelist["win_reg_demo"].motor == "registro"
    assert whitelist["win_reg_demo"].plantilla is None
    assert whitelist["lnx_demo"].motor == "comando"
    assert whitelist["lnx_demo"].parametros == {"familia": ["4", "6"]}


def test_construir_whitelist_sigue_rechazando_python(tmp_path):
    with pytest.raises(catalogo.CatalogoError, match="solo ejecuta herramientas"):
        executor.construir_whitelist(_catalogo_temporal(tmp_path, ENTRADA_PYTHON))


def test_las_25_herramientas_reales_son_de_motor_powershell():
    assert {spec.motor for spec in executor.WHITELIST.values()} == {"powershell"}


# --- Ningún comando fuera de los adaptadores ---------------------------------------------
WHITELIST_P7 = json.loads((FIXTURES / "whitelist_p7.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("tool_id", list(WHITELIST_P7))
def test_cada_herramienta_real_pasa_solo_por_el_adaptador_powershell_con_la_invocacion_exacta(tool_id, espias, monkeypatch):
    anterior = WHITELIST_P7[tool_id]
    params = {nombre: valores[0] for nombre, valores in anterior["parametros"].items()}
    texto = anterior["plantilla"].format(**params) if params else anterior["plantilla"]
    monkeypatch.setattr(executor, "_es_administrador", lambda: True)
    monkeypatch.setattr(powershell.sys, "platform", "win32")

    with patch("src.adaptadores.powershell.subprocess.run", return_value=_proceso()) as mock_run:
        resultado = executor.execute(tool_id, params)

    assert resultado["ok"] is True
    assert resultado["estado"] == "ok"
    assert resultado["comando"] == texto
    mock_run.assert_called_once()
    assert mock_run.call_args.args[0] == ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", texto]
    assert mock_run.call_args.kwargs["creationflags"] == powershell.CREATE_NO_WINDOW
    espias["powershell"].assert_called_once()
    espias["registro"].assert_not_called()
    espias["comando"].assert_not_called()


# --- Motor registro de principio a fin ---------------------------------------------------
def test_una_herramienta_de_registro_se_ejecuta_por_su_adaptador(usar_catalogo, espias, monkeypatch, ruta_audit_temporal):
    usar_catalogo(ENTRADA_REGISTRO)
    falso = WinregFalso(valor=1, tipo=4)
    monkeypatch.setattr(registro, "winreg", falso)

    with patch("src.adaptadores.powershell.subprocess.run") as mock_run:
        resultado = executor.execute("win_reg_demo", {})

    assert resultado["ok"] is True
    assert resultado["estado"] == "ok"
    assert resultado["data"] == {"existe": True, "valor": 1, "tipo": "REG_DWORD"}
    assert resultado["comando"] == r"HKLM\SOFTWARE\Policies\Demo\Valor"
    mock_run.assert_not_called()
    espias["registro"].assert_called_once()
    assert _leer_lineas_audit(ruta_audit_temporal)[0]["resultado"]["estado"] == "ok"


def test_un_valor_de_registro_inexistente_llega_como_dato(usar_catalogo, monkeypatch):
    usar_catalogo(ENTRADA_REGISTRO)
    monkeypatch.setattr(registro, "winreg", WinregFalso(error_abrir=FileNotFoundError(2, "no existe")))
    resultado = executor.execute("win_reg_demo", {})
    assert resultado["estado"] == "ok"
    assert resultado["data"] == {"existe": False, "valor": None, "tipo": None}


def test_sin_winreg_la_herramienta_de_registro_es_no_aplicable(usar_catalogo, monkeypatch):
    usar_catalogo(ENTRADA_REGISTRO)
    monkeypatch.setattr(registro, "winreg", None)
    resultado = executor.execute("win_reg_demo", {})
    assert resultado["ok"] is False
    assert resultado["estado"] == "no_aplicable"


def test_un_hive_alterado_en_memoria_no_llega_a_ejecutarse(usar_catalogo, espias, monkeypatch, ruta_audit_temporal):
    cat = usar_catalogo(ENTRADA_REGISTRO)
    entrada = cat.entradas["win_reg_demo"]
    monkeypatch.setitem(cat.entradas, "win_reg_demo", replace(entrada, clave_registro=ClaveRegistro("HKEY_EVIL", "x", "y")))

    resultado = executor.execute("win_reg_demo", {})

    assert resultado["estado"] == "error"
    espias["registro"].assert_not_called()
    assert _leer_lineas_audit(ruta_audit_temporal)[0]["motivo_rechazo"] == "hive_desconocido"


# --- Motor comando de principio a fin ----------------------------------------------------
def test_una_herramienta_de_comando_se_ejecuta_en_linux_por_su_adaptador(usar_catalogo, espias, monkeypatch):
    usar_catalogo(ENTRADA_COMANDO)
    monkeypatch.setattr(executor, "_capacidades", lambda: UBUNTU)

    with patch("src.adaptadores.comando.shutil.which", return_value="/usr/bin/ss"), \
         patch("src.adaptadores.comando.subprocess.run", return_value=_proceso("LISTEN 0 128")) as mock_run:
        resultado = executor.execute("lnx_demo", {"familia": "6"})

    assert resultado["estado"] == "ok"
    assert resultado["data"] == "LISTEN 0 128"
    assert resultado["comando"] == "ss -6 -tln"
    assert mock_run.call_args.args[0] == ["/usr/bin/ss", "-6", "-tln"]
    assert mock_run.call_args.kwargs["shell"] is False
    assert mock_run.call_args.kwargs["env"] == comando.ENTORNO_FIJO
    espias["comando"].assert_called_once()
    espias["powershell"].assert_not_called()


def test_el_comando_valida_sus_parametros_contra_el_enum(usar_catalogo, espias, monkeypatch):
    usar_catalogo(ENTRADA_COMANDO)
    monkeypatch.setattr(executor, "_capacidades", lambda: UBUNTU)
    resultado = executor.execute("lnx_demo", {"familia": "6; id"})
    assert resultado["estado"] == "error"
    espias["comando"].assert_not_called()


def test_binario_ausente_es_no_aplicable_y_no_una_excepcion(usar_catalogo, monkeypatch):
    usar_catalogo(ENTRADA_COMANDO)
    monkeypatch.setattr(executor, "_capacidades", lambda: UBUNTU)
    with patch("src.adaptadores.comando.shutil.which", return_value=None):
        resultado = executor.execute("lnx_demo", {"familia": "4"})
    assert resultado["ok"] is False
    assert resultado["estado"] == "no_aplicable"


def test_root_sin_ser_root_requiere_privilegios_sin_elevar(usar_catalogo, espias, monkeypatch, ruta_audit_temporal):
    usar_catalogo(ENTRADA_ROOT)
    monkeypatch.setattr(executor, "_capacidades", lambda: UBUNTU)
    resultado = executor.execute("lnx_root", {})
    assert resultado["estado"] == "requiere_privilegios"
    assert "root" in resultado["error"]
    espias["comando"].assert_not_called()
    assert _leer_lineas_audit(ruta_audit_temporal)[0]["motivo_rechazo"] == "requiere_admin"


def test_root_siendo_root_se_ejecuta(usar_catalogo, monkeypatch):
    usar_catalogo(ENTRADA_ROOT)
    monkeypatch.setattr(executor, "_capacidades", lambda: replace(UBUNTU, es_root=True))
    with patch("src.adaptadores.comando.shutil.which", return_value="/usr/sbin/sshd"), \
         patch("src.adaptadores.comando.subprocess.run", return_value=_proceso("port 22")):
        assert executor.execute("lnx_root", {})["estado"] == "ok"


def test_sudo_lo_frena_el_cargador_y_tambien_la_politica(tmp_path, usar_catalogo, espias, monkeypatch, ruta_audit_temporal):
    with pytest.raises(catalogo.CatalogoError, match="token denegado"):
        _catalogo_temporal(tmp_path, ENTRADA_SUDO)

    # Si el catálogo se altera en memoria tras cargarlo, la política lo rechaza en la llamada.
    cat = usar_catalogo(ENTRADA_COMANDO)
    monkeypatch.setitem(cat.entradas, "lnx_demo", replace(cat.entradas["lnx_demo"], argv=("sudo", "id"), parametros={}))
    monkeypatch.setattr(executor, "_capacidades", lambda: UBUNTU)

    resultado = executor.execute("lnx_demo", {})

    assert resultado["ok"] is False
    espias["comando"].assert_not_called()
    assert _leer_lineas_audit(ruta_audit_temporal)[0]["motivo_rechazo"] == "denegado_por_politica"


# --- Política en tiempo de ejecución (criterio 6) ----------------------------------------
def test_una_entrada_alterada_en_memoria_con_un_token_denegado_se_rechaza_y_se_audita(espias, monkeypatch, ruta_audit_temporal):
    entrada = executor.CATALOGO.entradas["get_defender_status"]
    monkeypatch.setitem(
        executor.CATALOGO.entradas, "get_defender_status", replace(entrada, plantilla=entrada.plantilla + "; IEX $x")
    )

    with patch("src.adaptadores.powershell.subprocess.run") as mock_run:
        resultado = executor.execute("get_defender_status", {})

    assert resultado["ok"] is False
    assert resultado["estado"] == "error"
    assert "IEX" in resultado["error"]
    mock_run.assert_not_called()
    espias["powershell"].assert_not_called()
    lineas = _leer_lineas_audit(ruta_audit_temporal)
    assert len(lineas) == 1
    assert lineas[0]["motivo_rechazo"] == "denegado_por_politica"
    assert "IEX" in lineas[0]["resultado"]["comando"]


def test_un_motor_incoherente_alterado_en_memoria_se_rechaza(espias, monkeypatch, ruta_audit_temporal):
    entrada = executor.CATALOGO.entradas["get_defender_status"]
    monkeypatch.setitem(executor.CATALOGO.entradas, "get_defender_status", replace(entrada, plataforma=Plataforma(so="linux")))
    monkeypatch.setattr(executor, "_capacidades", lambda: UBUNTU)

    resultado = executor.execute("get_defender_status", {})

    assert resultado["ok"] is False
    espias["powershell"].assert_not_called()
    assert _leer_lineas_audit(ruta_audit_temporal)[0]["motivo_rechazo"] == "motor_no_soportado"


def test_motor_python_se_rechaza_con_motivo_propio(usar_catalogo, espias, ruta_audit_temporal):
    usar_catalogo(ENTRADA_PYTHON)
    resultado = executor.execute("py_demo", {})
    assert resultado["estado"] == "error"
    assert not any(espia.called for espia in espias.values())
    assert _leer_lineas_audit(ruta_audit_temporal)[0]["motivo_rechazo"] == "motor_reservado"


def test_una_entrada_de_otro_perfil_es_no_aplicable_y_se_audita(usar_catalogo, espias, ruta_audit_temporal):
    usar_catalogo(ENTRADA_SISTEMAS)
    resultado = executor.execute("win_sistemas", {})
    assert resultado["ok"] is False
    assert resultado["estado"] == "no_aplicable"
    assert "perfil" in resultado["error"]
    espias["powershell"].assert_not_called()
    assert _leer_lineas_audit(ruta_audit_temporal)[0]["motivo_rechazo"] == "no_aplicable"


def test_una_herramienta_de_windows_en_linux_es_no_aplicable(espias, monkeypatch):
    monkeypatch.setattr(executor, "_capacidades", lambda: UBUNTU)
    resultado = executor.execute("get_defender_status", {})
    assert resultado["estado"] == "no_aplicable"
    espias["powershell"].assert_not_called()


# --- Clave `estado` en todos los caminos -------------------------------------------------
@pytest.mark.parametrize(
    "efecto, estado",
    [
        ({"return_value": _proceso('{"a": 1}')}, "ok"),
        ({"return_value": _proceso("no es json")}, "error"),
        ({"return_value": _proceso("", 1)}, "error"),
        ({"side_effect": FileNotFoundError()}, "no_aplicable"),
    ],
)
def test_el_resultado_lleva_el_estado_normalizado(efecto, estado):
    with patch("src.adaptadores.powershell.subprocess.run", **efecto):
        resultado = executor.execute("get_defender_status", {})
    assert resultado["estado"] == estado
    assert resultado["ok"] is (estado == "ok")
    assert list(resultado)[:6] == ["ok", "estado", "tool_id", "comando", "timestamp", "duracion_s"]


@pytest.mark.parametrize(
    "tool_id, params", [("borrar_disco", {}), ("start_quick_scan", {"foo": "bar"})]
)
def test_los_rechazos_de_validacion_tienen_estado_error(tool_id, params):
    assert executor.execute(tool_id, params)["estado"] == "error"


def test_sin_administrador_el_estado_es_requiere_privilegios(monkeypatch):
    monkeypatch.setattr(executor, "_es_administrador", lambda: False)
    resultado = executor.execute("start_quick_scan", {})
    assert resultado["estado"] == "requiere_privilegios"


def test_si_falla_la_auditoria_previa_el_estado_es_error(monkeypatch):
    monkeypatch.setattr(executor, "_es_administrador", lambda: True)
    with patch("src.adaptadores.powershell.subprocess.run") as mock_run, \
         patch.object(executor.audit, "registrar_auditoria", side_effect=OSError("disco lleno")):
        resultado = executor.execute("start_quick_scan", {})
    assert resultado["estado"] == "error"
    mock_run.assert_not_called()


# --- Detalles del executor ---------------------------------------------------------------
def test_sin_api_de_windows_no_se_considera_administrador(monkeypatch):
    monkeypatch.delattr(executor.ctypes, "windll", raising=False)
    assert executor._es_administrador() is False


def test_la_api_de_windows_decide_si_es_administrador(monkeypatch):
    windll = Mock()
    windll.shell32.IsUserAnAdmin.return_value = 1
    monkeypatch.setattr(executor.ctypes, "windll", windll, raising=False)
    assert executor._es_administrador() is True


def test_un_fallo_de_auditoria_en_una_lectura_solo_se_avisa(capsys):
    with patch("src.adaptadores.powershell.subprocess.run", return_value=_proceso()), \
         patch.object(executor.audit, "registrar_auditoria", side_effect=OSError("disco lleno")):
        resultado = executor.execute("get_defender_status", {})
    assert resultado["estado"] == "ok"
    assert "auditoría" in capsys.readouterr().err
