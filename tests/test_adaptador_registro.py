"""Tests del adaptador `registro` (regla 11, solo lectura).

Se sustituye el módulo `winreg` por un doble que registra todas las llamadas: así se comprueba
que solo se abren claves con `KEY_READ | KEY_WOW64_64KEY` y que ninguna función de escritura
llega a usarse, sin tocar el registro real del equipo.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from src import catalogo
from src.adaptadores import registro
from src.catalogo import ClaveRegistro

FUNCIONES_DE_ESCRITURA = (
    "SetValue", "SetValueEx", "CreateKey", "CreateKeyEx", "DeleteKey", "DeleteKeyEx",
    "DeleteValue", "SaveKey", "LoadKey", "ConnectRegistry", "FlushKey",
)  # fmt: skip


class _ClaveAbierta:
    def __enter__(self) -> "_ClaveAbierta":
        return self

    def __exit__(self, *_: object) -> None:
        return None


class WinregFalso:
    """Doble de `winreg` con constantes reales y lecturas programables."""

    HKEY_LOCAL_MACHINE = 0x80000002
    HKEY_CURRENT_USER = 0x80000001
    HKEY_CLASSES_ROOT = 0x80000000
    HKEY_USERS = 0x80000003
    HKEY_CURRENT_CONFIG = 0x80000005
    KEY_READ = 0x20019
    KEY_WOW64_64KEY = 0x0100

    def __init__(self, *, valor: object = 1, tipo: int = 4, error_abrir: Exception | None = None,
                 error_leer: Exception | None = None) -> None:  # fmt: skip
        self.valor, self.tipo = valor, tipo
        self.error_abrir, self.error_leer = error_abrir, error_leer
        self.llamadas: list[tuple[str, tuple[object, ...]]] = []

    def OpenKey(self, *args: object) -> _ClaveAbierta:  # noqa: N802 (nombre de winreg)
        self.llamadas.append(("OpenKey", args))
        if self.error_abrir is not None:
            raise self.error_abrir
        return _ClaveAbierta()

    def QueryValueEx(self, *args: object) -> tuple[object, int]:  # noqa: N802
        self.llamadas.append(("QueryValueEx", args))
        if self.error_leer is not None:
            raise self.error_leer
        return self.valor, self.tipo

    def __getattr__(self, nombre: str) -> object:
        if nombre in FUNCIONES_DE_ESCRITURA:
            raise AssertionError(f"el adaptador ha intentado usar winreg.{nombre}")
        raise AttributeError(nombre)


def _entrada(hive: str = "HKLM") -> catalogo.Entrada:
    base = catalogo.cargar_catalogo().entradas["get_defender_status"]
    return replace(
        base,
        id="win_uac",
        motor="registro",
        plantilla=None,
        clave_registro=ClaveRegistro(hive=hive, ruta=r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System", valor="EnableLUA"),
    )


@pytest.fixture
def winreg_falso(monkeypatch):
    def _instalar(**kwargs: object) -> WinregFalso:
        falso = WinregFalso(**kwargs)  # type: ignore[arg-type]
        monkeypatch.setattr(registro, "winreg", falso)
        return falso

    return _instalar


def test_construir_describe_la_clave_sin_tocar_el_registro():
    invocacion = registro.construir(_entrada(), {})
    assert invocacion.motor == "registro"
    assert invocacion.texto == r"HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System\EnableLUA"
    assert invocacion.clave.valor == "EnableLUA"


def test_construir_sin_clave_registro_falla():
    with pytest.raises(ValueError):
        registro.construir(replace(_entrada(), clave_registro=None), {})


def test_solo_abre_la_clave_con_key_read_y_vista_de_64_bits(winreg_falso):
    falso = winreg_falso()
    salida = registro.ejecutar(registro.construir(_entrada(), {}))

    assert salida.estado == "ok"
    assert [nombre for nombre, _ in falso.llamadas] == ["OpenKey", "QueryValueEx"]
    _, (raiz, ruta, reservado, acceso) = falso.llamadas[0]
    assert raiz == WinregFalso.HKEY_LOCAL_MACHINE
    assert ruta == r"SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"
    assert reservado == 0
    assert acceso == WinregFalso.KEY_READ | WinregFalso.KEY_WOW64_64KEY
    assert falso.llamadas[1][1][1] == "EnableLUA"


@pytest.mark.parametrize("hive", sorted(registro.HIVES))
def test_cada_hive_del_catalogo_se_traduce_a_su_constante(winreg_falso, hive):
    falso = winreg_falso()
    registro.ejecutar(registro.construir(_entrada(hive), {}))
    assert falso.llamadas[0][1][0] == getattr(WinregFalso, registro.HIVES[hive])


def test_el_mapa_de_hives_coincide_con_el_catalogo():
    assert set(registro.HIVES) == set(catalogo.HIVES)


@pytest.mark.parametrize(
    "valor, tipo, esperado",
    [
        (1, 4, {"existe": True, "valor": 1, "tipo": "REG_DWORD"}),
        ("1", 1, {"existe": True, "valor": "1", "tipo": "REG_SZ"}),
        (b"\x01\xff", 3, {"existe": True, "valor": "01ff", "tipo": "REG_BINARY"}),
        (["a", "b"], 7, {"existe": True, "valor": ["a", "b"], "tipo": "REG_MULTI_SZ"}),
        (5, 99, {"existe": True, "valor": 5, "tipo": "REG_99"}),
    ],
)
def test_un_valor_existente_se_devuelve_con_su_tipo(winreg_falso, valor, tipo, esperado):
    winreg_falso(valor=valor, tipo=tipo)
    salida = registro.ejecutar(registro.construir(_entrada(), {}))
    assert salida.estado == "ok"
    assert salida.datos == esperado


@pytest.mark.parametrize("donde", ["error_abrir", "error_leer"])
def test_una_clave_o_un_valor_inexistente_es_un_dato_no_un_error(winreg_falso, donde):
    winreg_falso(**{donde: FileNotFoundError(2, "no existe")})
    salida = registro.ejecutar(registro.construir(_entrada(), {}))
    assert salida.estado == "ok"
    assert salida.datos == {"existe": False, "valor": None, "tipo": None}


def test_acceso_denegado_requiere_privilegios(winreg_falso):
    winreg_falso(error_abrir=PermissionError(5, "Acceso denegado"))
    salida = registro.ejecutar(registro.construir(_entrada(), {}))
    assert salida.estado == "requiere_privilegios"
    assert "no eleva" in salida.error


def test_otro_fallo_del_sistema_es_error(winreg_falso):
    winreg_falso(error_leer=OSError(87, "parámetro incorrecto"))
    salida = registro.ejecutar(registro.construir(_entrada(), {}))
    assert salida.estado == "error"


def test_sin_winreg_es_no_aplicable(monkeypatch):
    monkeypatch.setattr(registro, "winreg", None)
    salida = registro.ejecutar(registro.construir(_entrada(), {}))
    assert salida.estado == "no_aplicable"


def test_un_hive_fuera_del_mapa_no_llega_a_ejecutarse(winreg_falso):
    falso = winreg_falso()
    salida = registro.ejecutar(registro.construir(_entrada("HKEY_EVIL"), {}))
    assert salida.estado == "error"
    assert falso.llamadas == []


def test_el_doble_detecta_un_intento_de_escritura():
    with pytest.raises(AssertionError):
        WinregFalso().SetValueEx  # noqa: B018 (se comprueba que el doble no pasa en vacío)


def test_al_importar_sin_winreg_el_modulo_queda_sin_registro(monkeypatch):
    import importlib
    import sys

    monkeypatch.setitem(sys.modules, "winreg", None)  # fuerza ImportError al importar
    try:
        importlib.reload(registro)
        assert registro.winreg is None
    finally:
        monkeypatch.undo()
        importlib.reload(registro)
    assert registro.winreg is not None or sys.platform != "win32"
