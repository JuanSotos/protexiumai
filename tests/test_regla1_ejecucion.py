"""Regla 1: fuera de `src/adaptadores/` ningún módulo ejecuta procesos ni abre el registro.

Recorre por AST todos los `.py` de `src/`, `app/` y, cuando exista, del paquete de la API de la
interfaz React (`api/`; si se crea dentro de `src/`, ya queda cubierto). Falla si algún módulo
fuera de los adaptadores:

- importa `subprocess` o `pty` (también con `__import__` o `importlib.import_module`);
- usa `os.system`, `os.popen`, `os.exec*`, `os.spawn*`, `os.posix_spawn*` u `os.startfile`;
- usa `asyncio.create_subprocess_*` o llamadas de Win32 que lanzan procesos (`ShellExecute*`,
  `CreateProcess*`, `WinExec`).

El registro de Windows (`winreg`) solo puede abrirse en dos sitios: el adaptador `registro`, que
ejecuta herramientas, y `src/plataforma/deteccion.py`, que lo lee para **detectar capacidades**
(build y edición de Windows) antes de que exista ninguna herramienta. Esta segunda excepción es
de lectura de detección, no de ejecución, y se declara con nombre propio en
`LECTURA_REGISTRO_DETECCION`. En ambos se exige además que no aparezca ninguna función ni
constante de escritura del registro.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
DIRECTORIOS = ("src", "app", "api")
ADAPTADORES = "src/adaptadores"
# Dentro de los adaptadores, solo estos dos lanzan procesos.
CON_SUBPROCESS = {"src/adaptadores/powershell.py", "src/adaptadores/comando.py"}
# Lectura del registro para ejecutar herramientas (adaptador) y para detectar capacidades.
LECTURA_REGISTRO_ADAPTADOR = {"src/adaptadores/registro.py"}
LECTURA_REGISTRO_DETECCION = {"src/plataforma/deteccion.py"}

MODULOS_PROHIBIDOS = {"subprocess", "pty"}
PREFIJOS_OS_PROHIBIDOS = ("system", "popen", "exec", "spawn", "posix_spawn", "startfile")
PREFIJOS_ASYNCIO_PROHIBIDOS = ("create_subprocess_",)
LLAMADAS_WIN32_PROHIBIDAS = ("ShellExecute", "CreateProcess", "WinExec")
ESCRITURA_REGISTRO = (
    "SetValue", "SetValueEx", "CreateKey", "CreateKeyEx", "DeleteKey", "DeleteKeyEx", "DeleteValue",
    "SaveKey", "LoadKey", "ConnectRegistry", "KEY_WRITE", "KEY_SET_VALUE", "KEY_CREATE_SUB_KEY",
    "KEY_ALL_ACCESS",
)  # fmt: skip


# --- Detector ----------------------------------------------------------------------------
def _raiz_modulo(nombre: str | None) -> str:
    return (nombre or "").split(".")[0]


def _nombre_atributo(nodo: ast.AST) -> str | None:
    """`os.system` → "os.system"; `a.b.c` → "a.b.c"; otra cosa → None."""
    partes: list[str] = []
    while isinstance(nodo, ast.Attribute):
        partes.append(nodo.attr)
        nodo = nodo.value
    if isinstance(nodo, ast.Name):
        partes.append(nodo.id)
        return ".".join(reversed(partes))
    return None


def _es_os_prohibido(nombre: str) -> bool:
    return nombre.startswith(PREFIJOS_OS_PROHIBIDOS)


def violaciones_de_ejecucion(codigo: str) -> list[str]:
    """Usos de ejecución de procesos en `codigo` (lista vacía si no hay ninguno)."""
    encontradas: list[str] = []
    for nodo in ast.walk(ast.parse(codigo)):
        if isinstance(nodo, ast.Import):
            encontradas += [f"import {a.name}" for a in nodo.names if _raiz_modulo(a.name) in MODULOS_PROHIBIDOS]
            encontradas += [f"import {a.name}" for a in nodo.names if a.name == "asyncio.subprocess"]
        elif isinstance(nodo, ast.ImportFrom):
            modulo = nodo.module or ""
            if _raiz_modulo(modulo) in MODULOS_PROHIBIDOS or modulo == "asyncio.subprocess":
                encontradas.append(f"from {modulo} import …")
            elif modulo == "os":
                encontradas += [f"from os import {a.name}" for a in nodo.names if _es_os_prohibido(a.name)]
            elif modulo == "asyncio":
                encontradas += [
                    f"from asyncio import {a.name}" for a in nodo.names
                    if a.name.startswith(PREFIJOS_ASYNCIO_PROHIBIDOS) or a.name == "subprocess"
                ]  # fmt: skip
        elif isinstance(nodo, ast.Attribute):
            nombre = _nombre_atributo(nodo) or ""
            if nombre.startswith("os.") and _es_os_prohibido(nombre[3:]):
                encontradas.append(nombre)
            elif nombre.startswith("asyncio.") and nombre[8:].startswith(PREFIJOS_ASYNCIO_PROHIBIDOS):
                encontradas.append(nombre)
            elif nodo.attr.startswith(LLAMADAS_WIN32_PROHIBIDAS):
                encontradas.append(nombre or nodo.attr)
        elif isinstance(nodo, ast.Call):
            funcion = _nombre_atributo(nodo.func)
            if funcion in ("__import__", "importlib.import_module", "import_module") and nodo.args:
                argumento = nodo.args[0]
                if isinstance(argumento, ast.Constant) and _raiz_modulo(str(argumento.value)) in MODULOS_PROHIBIDOS:
                    encontradas.append(f"{funcion}({argumento.value!r})")
    return encontradas


def usa_winreg(codigo: str) -> bool:
    """True si `codigo` importa `winreg` (directamente o con `__import__`)."""
    for nodo in ast.walk(ast.parse(codigo)):
        if isinstance(nodo, ast.Import) and any(a.name == "winreg" for a in nodo.names):
            return True
        if isinstance(nodo, ast.ImportFrom) and nodo.module == "winreg":
            return True
        if isinstance(nodo, ast.Call) and _nombre_atributo(nodo.func) in ("__import__", "importlib.import_module"):
            if nodo.args and isinstance(nodo.args[0], ast.Constant) and nodo.args[0].value == "winreg":
                return True
    return False


def escrituras_de_registro(codigo: str) -> list[str]:
    """Nombres de funciones o constantes de escritura de `winreg` que aparecen en `codigo`."""
    nombres = set()
    for nodo in ast.walk(ast.parse(codigo)):
        if isinstance(nodo, ast.Attribute):
            nombres.add(nodo.attr)
        elif isinstance(nodo, ast.Name):
            nombres.add(nodo.id)
        elif isinstance(nodo, ast.alias):
            nombres.add(nodo.name)
    return sorted(nombres & set(ESCRITURA_REGISTRO))


# --- Ficheros del proyecto ---------------------------------------------------------------
def _ficheros() -> dict[str, str]:
    """{ruta relativa con '/': código} de todos los .py de los directorios vigilados."""
    ficheros: dict[str, str] = {}
    for directorio in DIRECTORIOS:
        base = RAIZ / directorio
        if not base.is_dir():
            continue
        for ruta in sorted(base.rglob("*.py")):
            ficheros[ruta.relative_to(RAIZ).as_posix()] = ruta.read_text(encoding="utf-8")
    return ficheros


FICHEROS = _ficheros()


def _en_adaptadores(ruta: str) -> bool:
    return ruta.startswith(ADAPTADORES + "/")


def test_se_vigilan_los_paquetes_del_proyecto():
    assert any(r.startswith("src/") for r in FICHEROS)
    assert any(r.startswith("app/") for r in FICHEROS)
    assert "src/executor.py" in FICHEROS
    assert CON_SUBPROCESS | LECTURA_REGISTRO_ADAPTADOR | LECTURA_REGISTRO_DETECCION <= set(FICHEROS)


@pytest.mark.parametrize("ruta", [r for r in FICHEROS if not _en_adaptadores(r)])
def test_fuera_de_los_adaptadores_nadie_ejecuta_procesos(ruta):
    assert violaciones_de_ejecucion(FICHEROS[ruta]) == []


@pytest.mark.parametrize("ruta", [r for r in FICHEROS if _en_adaptadores(r) and r not in CON_SUBPROCESS])
def test_dentro_de_los_adaptadores_solo_powershell_y_comando_lanzan_procesos(ruta):
    assert violaciones_de_ejecucion(FICHEROS[ruta]) == []


@pytest.mark.parametrize("ruta", sorted(CON_SUBPROCESS))
def test_los_adaptadores_que_lanzan_procesos_no_usan_os_ni_shell(ruta):
    """Incluso en los adaptadores, solo `subprocess.run` en lista: nada de os.system ni pty."""
    codigo = FICHEROS[ruta]
    assert [v for v in violaciones_de_ejecucion(codigo) if "subprocess" not in v] == []
    assert "shell=True" not in codigo


def test_solo_el_adaptador_de_registro_y_la_deteccion_abren_el_registro():
    usan = {ruta for ruta, codigo in FICHEROS.items() if usa_winreg(codigo)}
    assert usan <= LECTURA_REGISTRO_ADAPTADOR | LECTURA_REGISTRO_DETECCION


@pytest.mark.parametrize("ruta", sorted(LECTURA_REGISTRO_ADAPTADOR | LECTURA_REGISTRO_DETECCION))
def test_quien_lee_el_registro_nunca_escribe(ruta):
    assert escrituras_de_registro(FICHEROS[ruta]) == []


# --- El detector no pasa en vacío --------------------------------------------------------
@pytest.mark.parametrize(
    "codigo",
    [
        "import subprocess",
        "import subprocess as sp",
        "from subprocess import run",
        "import pty",
        "import os\nos.system('dir')",
        "import os\nos.popen('dir')",
        "import os\nos.execv('/bin/x', [])",
        "import os\nos.spawnl(0, 'x')",
        "import os\nos.posix_spawn('x', [], {})",
        "import os\nos.startfile('x')",
        "from os import system",
        "from os import execvp",
        "import asyncio\nasyncio.create_subprocess_exec('x')",
        "from asyncio import create_subprocess_shell",
        "import asyncio.subprocess",
        "__import__('subprocess')",
        "import importlib\nimportlib.import_module('subprocess')",
        "import ctypes\nctypes.windll.shell32.ShellExecuteW(None, 'runas', 'x', None, None, 1)",
        "import ctypes\nctypes.windll.kernel32.CreateProcessW()",
        "import ctypes\nctypes.windll.kernel32.WinExec(b'x', 0)",
    ],
)
def test_el_detector_caza_cada_forma_de_ejecutar(codigo):
    assert violaciones_de_ejecucion(codigo) != []


@pytest.mark.parametrize(
    "codigo",
    [
        "import os\nos.environ.get('X')",
        "import os\nos.path.join('a', 'b')",
        "import shutil\nshutil.which('ls')",
        "import ctypes\nctypes.windll.shell32.IsUserAnAdmin()",
        "import importlib\nimportlib.import_module('json')",
    ],
)
def test_el_detector_no_da_falsos_positivos_con_usos_inocuos(codigo):
    assert violaciones_de_ejecucion(codigo) == []


@pytest.mark.parametrize(
    "codigo", ["import winreg", "from winreg import OpenKey", "__import__('winreg')"]
)
def test_el_detector_ve_el_registro(codigo):
    assert usa_winreg(codigo)


@pytest.mark.parametrize(
    "codigo",
    [
        "import winreg\nwinreg.SetValueEx(k, 'v', 0, 4, 1)",
        "import winreg\nwinreg.CreateKey(k, 'x')",
        "import winreg\nwinreg.DeleteValue(k, 'v')",
        "import winreg\nwinreg.OpenKey(k, 'x', 0, winreg.KEY_SET_VALUE)",
        "from winreg import KEY_ALL_ACCESS",
    ],
)
def test_el_detector_caza_las_escrituras_de_registro(codigo):
    assert escrituras_de_registro(codigo) != []
