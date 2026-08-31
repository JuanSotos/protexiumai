"""Tests de src/tools_schema.py: el schema de function calling se genera desde executor.WHITELIST."""

from __future__ import annotations

import json

from src import executor
from src.executor import ToolSpec
from src.tools_schema import generar_tools_schema


def test_schema_tiene_una_entrada_por_tool_de_whitelist():
    schema = generar_tools_schema()
    assert {t["function"]["name"] for t in schema} == set(executor.WHITELIST)


def test_schema_usa_type_function_en_cada_entrada():
    schema = generar_tools_schema()
    assert all(t["type"] == "function" for t in schema)


def test_descripcion_coincide_con_la_whitelist():
    schema = generar_tools_schema()
    por_nombre = {t["function"]["name"]: t["function"] for t in schema}
    for tool_id, spec in executor.WHITELIST.items():
        assert por_nombre[tool_id]["description"] == spec.descripcion


def test_tool_sin_parametros_tiene_properties_y_required_vacios():
    schema = generar_tools_schema()
    por_nombre = {t["function"]["name"]: t["function"] for t in schema}
    parametros = por_nombre["get_defender_status"]["parameters"]
    assert parametros["properties"] == {}
    assert parametros["required"] == []


def test_tool_con_parametros_genera_enum_correcto():
    schema = generar_tools_schema()
    por_nombre = {t["function"]["name"]: t["function"] for t in schema}
    parametros = por_nombre["set_firewall_profile"]["parameters"]

    assert parametros["properties"]["profile"] == {
        "type": "string",
        "enum": ["Domain", "Private", "Public"],
    }
    assert parametros["properties"]["enabled"] == {
        "type": "string",
        "enum": ["True", "False"],
    }
    assert parametros["required"] == ["profile", "enabled"]


def test_tool_start_custom_scan_genera_enum_correcto():
    schema = generar_tools_schema()
    por_nombre = {t["function"]["name"]: t["function"] for t in schema}
    parametros = por_nombre["start_custom_scan"]["parameters"]

    assert parametros["properties"]["ruta"] == {
        "type": "string",
        "enum": ["Descargas", "Escritorio", "Documentos"],
    }
    assert parametros["required"] == ["ruta"]


def test_tool_start_full_scan_sin_parametros():
    schema = generar_tools_schema()
    por_nombre = {t["function"]["name"]: t["function"] for t in schema}
    parametros = por_nombre["start_full_scan"]["parameters"]
    assert parametros["properties"] == {}
    assert parametros["required"] == []


def test_schema_es_json_serializable():
    schema = generar_tools_schema()
    json.dumps(schema)


def test_fuente_unica_de_verdad(monkeypatch):
    whitelist_de_prueba = {
        "tool_de_prueba": ToolSpec(
            id="tool_de_prueba",
            descripcion="Herramienta de prueba.",
            plantilla="Get-Algo",
            parametros={"modo": ["A", "B"]},
            nivel="lectura",
        ),
    }
    monkeypatch.setattr(executor, "WHITELIST", whitelist_de_prueba)

    schema = generar_tools_schema()

    assert len(schema) == 1
    assert schema[0]["function"]["name"] == "tool_de_prueba"
    assert schema[0]["function"]["parameters"]["properties"]["modo"]["enum"] == ["A", "B"]
