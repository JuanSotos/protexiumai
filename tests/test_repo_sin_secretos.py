"""Tests de higiene del repositorio: ni claves de API ni .env versionados.

Usan `git ls-files` (solo lectura) para recorrer lo que acabaría en el repositorio.
Los mensajes de fallo indican fichero y línea, pero nunca el valor sospechoso.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
TAMANO_MAXIMO_BYTES = 2_000_000

PATRON_GROQ = re.compile(r"gsk_[A-Za-z0-9]{20,}")
PATRON_SK = re.compile(r"sk-[A-Za-z0-9]{20,}")
# api_key / token / secret asignados a un literal entrecomillado de 16 o más caracteres.
PATRON_ASIGNACION = re.compile(
    r"""(?ix)
    (?:api[_-]?key|token|secret)["']?     # nombre sospechoso (con comilla de cierre si es clave de dict/JSON)
    \s*[:=]\s*
    (?:f|r|b)?["']([^"'\s]{16,})["']      # literal de 16 o más caracteres sin espacios
    """
)
PATRONES = {
    "clave tipo Groq (gsk_...)": PATRON_GROQ,
    "clave tipo OpenAI (sk-...)": PATRON_SK,
    "asignación de api_key/token con literal largo": PATRON_ASIGNACION,
}

# Valores aceptables en .env.example para claves sensibles: vacío o un marcador evidente.
PATRON_MARCADOR_EJEMPLO = re.compile(r"(?i)^(tu[_-].*|your[_-].*|changeme|example.*|xxx+|<.*>|ollama)$")
PATRON_CLAVE_SENSIBLE = re.compile(r"(?i)(key|token|secret|password)")


def _git(*args: str) -> list[str]:
    """Ejecuta un `git` de solo lectura en la raíz del repositorio y devuelve las líneas de salida."""
    try:
        proceso = subprocess.run(
            ["git", *args], cwd=RAIZ, capture_output=True, text=True, encoding="utf-8", timeout=30
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pytest.skip("git no está disponible")
    if proceso.returncode != 0:
        pytest.skip("el directorio no es un repositorio git")
    return proceso.stdout.splitlines()


def _ficheros_a_escanear() -> list[Path]:
    """Ficheros versionados más los nuevos no ignorados (los que entrarían en el próximo commit)."""
    rutas = _git("ls-files", "--cached", "--others", "--exclude-standard")
    return [RAIZ / r for r in rutas if (RAIZ / r).is_file()]


def _leer_texto(ruta: Path) -> str | None:
    """Devuelve el texto del fichero, o None si es binario, demasiado grande o ilegible."""
    try:
        if ruta.stat().st_size > TAMANO_MAXIMO_BYTES:
            return None
        datos = ruta.read_bytes()
    except OSError:
        return None
    if b"\x00" in datos:
        return None
    return datos.decode("utf-8", errors="ignore")


def test_env_no_esta_versionado() -> None:
    """El fichero .env (con la API key real) nunca debe estar en el índice de git."""
    versionados = _git("ls-files", "--cached")
    assert ".env" not in versionados, ".env está versionado: retíralo con `git rm --cached .env`"


def test_ningun_fichero_contiene_claves() -> None:
    """Ningún fichero versionado (ni pendiente de versionar) contiene patrones de clave de API."""
    hallazgos: list[str] = []
    for ruta in _ficheros_a_escanear():
        texto = _leer_texto(ruta)
        if texto is None:
            continue
        relativa = ruta.relative_to(RAIZ).as_posix()
        for numero, linea in enumerate(texto.splitlines(), start=1):
            for nombre, patron in PATRONES.items():
                if patron.search(linea):
                    hallazgos.append(f"{relativa}:{numero}: {nombre}")
    assert not hallazgos, "Posibles secretos en el repositorio:\n" + "\n".join(hallazgos)


def test_env_example_solo_tiene_valores_vacios_o_de_ejemplo() -> None:
    """En .env.example las claves sensibles van vacías o con un marcador de ejemplo evidente."""
    texto = (RAIZ / ".env.example").read_text(encoding="utf-8")
    incorrectas: list[str] = []
    for numero, linea in enumerate(texto.splitlines(), start=1):
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        nombre, valor = (parte.strip() for parte in linea.split("=", 1))
        if PATRON_CLAVE_SENSIBLE.search(nombre) and valor and not PATRON_MARCADOR_EJEMPLO.match(valor):
            incorrectas.append(f".env.example:{numero}: {nombre} tiene un valor que no parece un ejemplo")
    assert not incorrectas, "\n".join(incorrectas)


@pytest.mark.parametrize(
    "linea",
    [
        'GROQ = "gsk_' + "A" * 24 + '"',
        'clave = "sk-' + "b" * 24 + '"',
        'api_key = "' + "c" * 20 + '"',
        "{'token': '" + "d" * 18 + "'}",
    ],
)
def test_los_patrones_detectan_claves_falsas(linea: str) -> None:
    """Comprobación de los propios patrones con claves sintéticas (no son claves reales)."""
    assert any(patron.search(linea) for patron in PATRONES.values())


@pytest.mark.parametrize(
    "linea",
    [
        'OLLAMA_API_KEY = "ollama"',
        "api_key = os.environ.get('GROQ_API_KEY', '')",
        'token = ""',
    ],
)
def test_los_patrones_no_marcan_valores_inocuos(linea: str) -> None:
    """Valores cortos, vacíos o leídos del entorno no son literales sospechosos."""
    assert not any(patron.search(linea) for patron in PATRONES.values())
