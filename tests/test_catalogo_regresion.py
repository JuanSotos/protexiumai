"""Regresión de la migración WHITELIST en código → catálogo YAML (P8) y presupuesto de tokens.

Comparan el comportamiento actual con las instantáneas de P7 (`tests/fixtures/`), generadas
con el código anterior a la migración: `schema_p7.json` (esquema que ve el LLM) y
`whitelist_p7.json` (plantillas, niveles, administrador y timeouts de las 25 herramientas).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src import catalogo, executor
from src.tools_schema import generar_tools_schema

FIXTURES = Path(__file__).parent / "fixtures"
LIMITE_TOKENS_ESQUEMA = 3000

# Diferencias de redacción aceptadas entre el esquema de P7 y el actual: {tool_id: motivo}.
# Vacío: la migración conserva literalmente las 25 descripciones.
DIFERENCIAS_DE_REDACCION: dict[str, str] = {}


def _cargar(nombre: str) -> Any:
    return json.loads((FIXTURES / nombre).read_text(encoding="utf-8"))


def _normalizar(esquema: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Reduce el esquema a nombre → (descripción, {parámetro: {valores}}, {obligatorios}), sin orden."""
    resultado: dict[str, dict[str, Any]] = {}
    for tool in esquema:
        assert tool["type"] == "function"
        funcion = tool["function"]
        parametros = funcion["parameters"]
        assert parametros["type"] == "object"
        resultado[funcion["name"]] = {
            "descripcion": funcion["description"],
            "propiedades": {
                nombre: (propiedad["type"], frozenset(propiedad["enum"]))
                for nombre, propiedad in parametros["properties"].items()
            },
            "obligatorios": frozenset(parametros["required"]),
        }
    return resultado


def medir_tokens_esquema() -> int:
    """Aproxima los tokens del esquema: caracteres del JSON compacto (UTF-8) divididos entre 4."""
    compacto = json.dumps(generar_tools_schema(), ensure_ascii=False, separators=(",", ":"))
    return len(compacto) // 4


# --- Esquema del LLM ---------------------------------------------------------------------
def test_esquema_equivale_semanticamente_al_de_p7():
    actual = _normalizar(generar_tools_schema())
    esperado = _normalizar(_cargar("schema_p7.json"))

    assert set(actual) == set(esperado), "mismos nombres de herramienta"
    for nombre, tool_esperada in esperado.items():
        tool_actual = actual[nombre]
        assert tool_actual["propiedades"] == tool_esperada["propiedades"], f"{nombre}: parámetros y enums"
        assert tool_actual["obligatorios"] == tool_esperada["obligatorios"], f"{nombre}: obligatorios"
        if nombre not in DIFERENCIAS_DE_REDACCION:
            assert tool_actual["descripcion"] == tool_esperada["descripcion"], f"{nombre}: redacción"


def test_el_orden_de_las_herramientas_y_de_los_enums_tambien_se_conserva():
    """Más estricto que la equivalencia semántica: el orden alimenta al LLM tal cual."""
    assert generar_tools_schema() == _cargar("schema_p7.json")


def test_las_diferencias_de_redaccion_declaradas_son_reales():
    esperado = _normalizar(_cargar("schema_p7.json"))
    actual = _normalizar(generar_tools_schema())
    for nombre in DIFERENCIAS_DE_REDACCION:
        assert actual[nombre]["descripcion"] != esperado[nombre]["descripcion"], nombre


# --- WHITELIST derivada ------------------------------------------------------------------
def test_whitelist_derivada_conserva_plantillas_niveles_admin_y_timeouts():
    esperado = _cargar("whitelist_p7.json")
    assert list(executor.WHITELIST) == list(esperado)
    for tool_id, spec in executor.WHITELIST.items():
        anterior = esperado[tool_id]
        assert spec.id == anterior["id"]
        assert spec.plantilla == anterior["plantilla"], tool_id
        assert spec.descripcion == anterior["descripcion"], tool_id
        assert spec.parametros == anterior["parametros"], tool_id
        assert spec.nivel == anterior["nivel"], tool_id
        assert spec.requiere_admin == anterior["requiere_admin"], tool_id
        assert spec.timeout_s == anterior["timeout_s"], tool_id


def test_whitelist_derivada_cuenta_niveles_y_administrador_como_en_p7():
    niveles = [spec.nivel for spec in executor.WHITELIST.values()]
    assert (niveles.count("lectura"), niveles.count("accion"), niveles.count("mutante")) == (17, 4, 4)
    assert sum(spec.requiere_admin for spec in executor.WHITELIST.values()) == 12


def test_whitelist_se_construye_desde_el_catalogo():
    cat = catalogo.cargar_catalogo()
    assert set(executor.WHITELIST) == set(cat.herramientas_llm())


def test_executor_rechaza_una_herramienta_que_no_sabe_ejecutar(tmp_path):
    (tmp_path / "herramientas_llm.yaml").write_text(
        "version: 1\n"
        "entradas:\n"
        "  - id: lnx_demo\n"
        "    titulo: Demo\n"
        "    descripcion_llm: Demo.\n"
        "    justificacion: Demo.\n"
        "    tipo: herramienta\n"
        "    nivel: lectura\n"
        "    riesgo: bajo\n"
        "    sensibilidad: tecnica\n"
        "    perfiles: [hogar]\n"
        "    plataforma: {so: linux}\n"
        "    requisitos: {privilegios: usuario}\n"
        "    motor: comando\n"
        "    argv: [uname]\n"
        "    area: sistema\n",
        encoding="utf-8",
    )
    with pytest.raises(catalogo.CatalogoError, match="solo ejecuta herramientas"):
        executor.construir_whitelist(catalogo.cargar_catalogo(tmp_path))


def test_el_comando_generado_sigue_siendo_la_plantilla_con_los_valores_validados(monkeypatch):
    llamadas: list[list[str]] = []

    class Proceso:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr(executor, "_es_administrador", lambda: True)
    monkeypatch.setattr(executor.subprocess, "run", lambda comando, **_: llamadas.append(comando) or Proceso())

    resultado = executor.execute("set_firewall_profile", {"profile": "Public", "enabled": "False"})

    assert resultado["ok"] is True
    assert llamadas[0][-1] == "Set-NetFirewallProfile -Profile Public -Enabled False"


# --- Presupuesto de tokens ---------------------------------------------------------------
def test_el_esquema_cabe_en_el_presupuesto_de_tokens():
    """Límite de 8.000 tokens/minuto del plan gratuito de Groq: el esquema no pasa de 3.000."""
    tokens = medir_tokens_esquema()
    assert tokens <= LIMITE_TOKENS_ESQUEMA, f"esquema de ~{tokens} tokens (límite {LIMITE_TOKENS_ESQUEMA})"


def test_la_medida_de_tokens_detecta_un_esquema_desmesurado(monkeypatch):
    descripcion_larga = "x" * (4 * LIMITE_TOKENS_ESQUEMA)
    spec = executor.ToolSpec(id="t", descripcion=descripcion_larga, plantilla="Get-Date")
    monkeypatch.setattr(executor, "WHITELIST", {"t": spec})
    assert medir_tokens_esquema() > LIMITE_TOKENS_ESQUEMA
