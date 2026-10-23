"""Tests de src/catalogo.py: carga válida, causas de rechazo, lista de denegación y fusión de marcos.

Los catálogos de prueba se escriben en directorios temporales; ninguno ejecuta comandos.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from src import catalogo
from src.catalogo import CatalogoError

QUITAR = object()  # marca para eliminar un campo de la entrada base


def entrada_base(**cambios: Any) -> dict[str, Any]:
    """Entrada válida mínima (herramienta de lectura sin parámetros); `cambios` la modifica."""
    entrada: dict[str, Any] = {
        "id": "get_prueba",
        "titulo": "Prueba",
        "descripcion_llm": "Herramienta de prueba.",
        "justificacion": "Existe solo en los tests.",
        "tipo": "herramienta",
        "nivel": "lectura",
        "riesgo": "bajo",
        "sensibilidad": "tecnica",
        "perfiles": ["hogar"],
        "plataforma": {"so": "windows"},
        "requisitos": {"privilegios": "usuario"},
        "motor": "powershell",
        "plantilla": "Get-Date | ConvertTo-Json",
        "area": "sistema",
    }
    for clave, valor in cambios.items():
        if valor is QUITAR:
            entrada.pop(clave, None)
        else:
            entrada[clave] = valor
    return entrada


def entrada_con_parametros(**cambios: Any) -> dict[str, Any]:
    base = {
        "plantilla": "Set-NetFirewallProfile -Profile {profile} -Enabled {enabled}",
        "parametros": {"profile": ["Domain", "Public"], "enabled": ["True", "False"]},
        "nivel": "mutante",
        "riesgo": "alto",
    }
    base.update(cambios)
    return entrada_base(**base)


def escribir(raiz: Path, entradas: list[dict[str, Any]], ruta: str = "herramientas_llm.yaml") -> Path:
    destino = raiz / ruta
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        yaml.safe_dump({"version": 1, "entradas": entradas}, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    return destino


def cargar(raiz: Path, entradas: list[dict[str, Any]]) -> catalogo.Catalogo:
    escribir(raiz, entradas)
    return catalogo.cargar_catalogo(raiz)


def rechaza(raiz: Path, entradas: list[dict[str, Any]], *fragmentos: str) -> str:
    """Comprueba que el catálogo se rechaza y que el mensaje contiene todos los fragmentos."""
    escribir(raiz, entradas)
    with pytest.raises(CatalogoError) as excepcion:
        catalogo.cargar_catalogo(raiz)
    mensaje = str(excepcion.value)
    for fragmento in fragmentos:
        assert fragmento in mensaje, f"falta {fragmento!r} en: {mensaje}"
    return mensaje


# --- Carga válida ------------------------------------------------------------------------
def test_catalogo_real_carga_las_25_herramientas():
    cat = catalogo.cargar_catalogo()
    assert len(cat.entradas) == 25
    assert set(cat.herramientas_llm()) == set(cat.entradas)
    assert all(e.tipo == "herramienta" and e.motor == "powershell" for e in cat.entradas.values())


def test_catalogo_real_cumple_el_patron_de_id_y_los_perfiles():
    for entrada in catalogo.cargar_catalogo().entradas.values():
        assert catalogo.PATRON_ID.match(entrada.id)
        assert set(entrada.perfiles) <= set(catalogo.PERFILES)


def test_carga_valida_minima(tmp_path):
    cat = cargar(tmp_path, [entrada_base()])
    entrada = cat.entradas["get_prueba"]
    assert entrada.timeout_s == catalogo.TIMEOUT_POR_DEFECTO_S
    assert entrada.parametros == {}
    assert entrada.marcos == catalogo.Marcos()
    assert entrada.origen == "herramientas_llm.yaml"


def test_carga_valida_con_parametros(tmp_path):
    entrada = cargar(tmp_path, [entrada_con_parametros()]).entradas["get_prueba"]
    assert entrada.parametros == {"profile": ("Domain", "Public"), "enabled": ("True", "False")}


def test_catalogo_sin_fichero_de_herramientas_falla(tmp_path):
    with pytest.raises(CatalogoError, match="herramientas_llm.yaml"):
        catalogo.cargar_catalogo(tmp_path)


def test_carpetas_windows_y_linux_vacias_son_validas(tmp_path):
    escribir(tmp_path, [entrada_base()])
    (tmp_path / "windows").mkdir()
    (tmp_path / "linux").mkdir()
    (tmp_path / "windows" / ".gitkeep").touch()
    assert len(catalogo.cargar_catalogo(tmp_path).entradas) == 1


def test_comprobacion_valida_en_carpeta_windows(tmp_path):
    escribir(tmp_path, [entrada_base()])
    comprobacion = entrada_base(
        id="win_firewall_activo", tipo="comprobacion", severidad="alta", peso=10, area="red"
    )
    escribir(tmp_path, [comprobacion], "windows/red.yaml")
    cat = catalogo.cargar_catalogo(tmp_path)
    assert cat.entradas["win_firewall_activo"].origen == "windows/red.yaml"
    assert "win_firewall_activo" not in cat.herramientas_llm()


def test_entrada_linux_con_comando_y_registro_windows_validas(tmp_path):
    escribir(tmp_path, [entrada_base()])
    linux = entrada_base(
        id="lnx_ssh_root", tipo="comprobacion", severidad="media", peso=5, area="cuentas",
        plataforma={"so": "linux", "familias": ["debian", "rhel"]},
        requisitos={"privilegios": "root", "binarios": ["sshd"]},
        motor="comando", plantilla=QUITAR, argv=["sshd", "-T"],
    )  # fmt: skip
    registro = entrada_base(
        id="win_uac", tipo="comprobacion", severidad="alta", peso=8, area="sistema", motor="registro",
        plantilla=QUITAR,
        clave_registro={"hive": "HKLM", "ruta": "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System", "valor": "EnableLUA"},
        plataforma={"so": "windows", "build_min": 22000, "ediciones": ["Pro", "Home"]},
    )  # fmt: skip
    escribir(tmp_path, [linux], "linux/ssh.yaml")
    escribir(tmp_path, [registro], "windows/uac.yaml")
    cat = catalogo.cargar_catalogo(tmp_path)
    assert cat.entradas["lnx_ssh_root"].argv == ("sshd", "-T")
    assert cat.entradas["win_uac"].clave_registro.valor == "EnableLUA"


# --- Causas de rechazo -------------------------------------------------------------------
def test_rechaza_campo_desconocido(tmp_path):
    rechaza(tmp_path, [entrada_base(inventado="x")], "herramientas_llm.yaml", "get_prueba", "campo desconocido 'inventado'")


def test_rechaza_campo_desconocido_en_bloque_anidado(tmp_path):
    rechaza(tmp_path, [entrada_base(plataforma={"so": "windows", "kernel": 6})], "campo desconocido 'kernel'", "plataforma")
    rechaza(tmp_path, [entrada_base(requisitos={"privilegios": "usuario", "uid": 0})], "campo desconocido 'uid'")


def test_rechaza_campo_desconocido_en_la_cabecera(tmp_path):
    (tmp_path / "herramientas_llm.yaml").write_text("version: 1\nentradas: []\nextra: 1\n", encoding="utf-8")
    with pytest.raises(CatalogoError, match="campo desconocido 'extra'"):
        catalogo.cargar_catalogo(tmp_path)


def test_rechaza_version_de_esquema_incorrecta(tmp_path):
    (tmp_path / "herramientas_llm.yaml").write_text("version: 2\nentradas: []\n", encoding="utf-8")
    with pytest.raises(CatalogoError, match="'version' debe ser 1"):
        catalogo.cargar_catalogo(tmp_path)


@pytest.mark.parametrize("campo", list(catalogo.CAMPOS_OBLIGATORIOS))
def test_rechaza_campo_obligatorio_ausente(tmp_path, campo):
    rechaza(tmp_path, [entrada_base(**{campo: QUITAR})], f"falta el campo obligatorio '{campo}'")


def test_rechaza_ids_duplicados_en_el_mismo_fichero(tmp_path):
    rechaza(tmp_path, [entrada_base(), entrada_base()], "id duplicado", "get_prueba")


def test_rechaza_ids_duplicados_entre_ficheros(tmp_path):
    escribir(tmp_path, [entrada_base(id="win_x", tipo="comprobacion", severidad="baja", peso=1)], "windows/a.yaml")
    escribir(tmp_path, [entrada_base(id="win_x", tipo="comprobacion", severidad="baja", peso=1)], "windows/b.yaml")
    escribir(tmp_path, [entrada_base()])
    with pytest.raises(CatalogoError) as excepcion:
        catalogo.cargar_catalogo(tmp_path)
    assert "windows/b.yaml" in str(excepcion.value) and "windows/a.yaml" in str(excepcion.value)


def test_rechaza_clave_duplicada_en_el_yaml(tmp_path):
    (tmp_path / "herramientas_llm.yaml").write_text("version: 1\nversion: 1\nentradas: []\n", encoding="utf-8")
    with pytest.raises(CatalogoError, match="clave duplicada"):
        catalogo.cargar_catalogo(tmp_path)


def test_rechaza_yaml_mal_formado(tmp_path):
    (tmp_path / "herramientas_llm.yaml").write_text("version: [1\n", encoding="utf-8")
    with pytest.raises(CatalogoError, match="YAML inválido"):
        catalogo.cargar_catalogo(tmp_path)


@pytest.mark.parametrize(
    "campo, valor",
    [
        ("tipo", "otra"),
        ("nivel", "critico"),
        ("riesgo", "medio"),
        ("sensibilidad", "secreta"),
        ("motor", "bash"),
        ("area", "cocina"),
        ("severidad", "critica"),
        ("perfiles", ["hogar", "empresa"]),
        ("perfiles", []),
        ("perfiles", ["hogar", "hogar"]),
        ("plataforma", {"so": "macos"}),
        ("requisitos", {"privilegios": "superusuario"}),
    ],
)
def test_rechaza_enum_invalido(tmp_path, campo, valor):
    rechaza(tmp_path, [entrada_base(**{campo: valor})], "get_prueba")


@pytest.mark.parametrize("id_", ["", "con espacio", "tilde_ñ", "a;b", "x" * 65, "a/b"])
def test_rechaza_id_con_formato_invalido(tmp_path, id_):
    escribir(tmp_path, [entrada_base(id=id_)])
    with pytest.raises(CatalogoError):
        catalogo.cargar_catalogo(tmp_path)


def test_acepta_id_de_64_caracteres(tmp_path):
    assert "a" * 64 in cargar(tmp_path, [entrada_base(id="a" * 64)]).entradas


def test_rechaza_marcador_no_declarado_con_parametros(tmp_path):
    entrada = entrada_con_parametros(plantilla="Set-NetFirewallProfile -Profile {profile} -Enabled {otro}")
    rechaza(tmp_path, [entrada], "{otro}", "sin declarar")


def test_rechaza_marcador_no_declarado_sin_parametros(tmp_path):
    rechaza(tmp_path, [entrada_base(plantilla="Get-Item {ruta}")], "{ruta}", "sin declarar")


def test_rechaza_parametro_declarado_pero_no_usado(tmp_path):
    entrada = entrada_con_parametros(plantilla="Set-NetFirewallProfile -Profile {profile}")
    rechaza(tmp_path, [entrada], "no usados", "enabled")


@pytest.mark.parametrize("marcador", ["{profile!r}", "{profile:>10}", "{profile.upper}", "{}", "{0}", "{profile[0]}"])
def test_rechaza_marcadores_con_formato_o_accesos(tmp_path, marcador):
    entrada = entrada_con_parametros(plantilla=f"Set-NetFirewallProfile -Profile {marcador} -Enabled {{enabled}}")
    rechaza(tmp_path, [entrada])


def test_llaves_de_powershell_sin_parametros_son_literales(tmp_path):
    plantilla = "Get-Volume | Where-Object { $_.DriveLetter } | ConvertTo-Json"
    assert cargar(tmp_path, [entrada_base(plantilla=plantilla)]).entradas["get_prueba"].plantilla == plantilla


def test_llaves_dobles_con_parametros_son_literales(tmp_path):
    plantilla = "$r = @{{ 'a' = 'b' }}; Get-Item $r['{profile}']"
    entrada = entrada_base(plantilla=plantilla, parametros={"profile": ["Domain"]})
    assert cargar(tmp_path, [entrada]).entradas["get_prueba"].plantilla == plantilla


def test_rechaza_llave_simple_de_powershell_con_parametros(tmp_path):
    entrada = entrada_base(plantilla="Get-Volume | Where-Object { $_.X } # {profile}", parametros={"profile": ["Domain"]})
    rechaza(tmp_path, [entrada])


def test_rechaza_booleanos_yaml_sin_comillar(tmp_path):
    crudo = yaml.safe_dump({"version": 1, "entradas": [entrada_con_parametros()]}, sort_keys=False)
    (tmp_path / "herramientas_llm.yaml").write_text(
        crudo.replace("'True'", "true").replace("'False'", "false"), encoding="utf-8"
    )
    with pytest.raises(CatalogoError, match="comillar"):
        catalogo.cargar_catalogo(tmp_path)


@pytest.mark.parametrize("valor", ["a b", "a;b", "$x", "'x'", '"x"', "-Recurse", "../x", "x\ny", ""])
def test_rechaza_valores_de_enum_peligrosos(tmp_path, valor):
    rechaza(tmp_path, [entrada_con_parametros(parametros={"profile": ["Domain", valor], "enabled": ["True"]})])


def test_rechaza_enum_vacio_y_repetido(tmp_path):
    rechaza(tmp_path, [entrada_con_parametros(parametros={"profile": [], "enabled": ["True"]})], "vacío")
    rechaza(tmp_path, [entrada_con_parametros(parametros={"profile": ["A", "A"], "enabled": ["True"]})], "repetidos")


def test_rechaza_nombre_de_parametro_invalido(tmp_path):
    entrada = entrada_base(plantilla="Get-Item {Mal}", parametros={"Mal": ["x"]})
    rechaza(tmp_path, [entrada], "nombre de parámetro")


def test_rechaza_campos_incompatibles_con_el_motor(tmp_path):
    rechaza(tmp_path, [entrada_base(argv=["x"])], "'argv' no es válido con motor 'powershell'")
    rechaza(tmp_path, [entrada_base(plantilla=QUITAR)], "plantilla")
    rechaza(tmp_path, [entrada_base(motor="registro", plantilla=QUITAR)], "clave_registro")
    rechaza(tmp_path, [entrada_base(motor="comando", plantilla=QUITAR, argv=[])], "argv")


def test_rechaza_incoherencias_de_tipo_nivel_y_plataforma(tmp_path):
    rechaza(tmp_path, [entrada_base(tipo="comprobacion", nivel="mutante", severidad="alta", peso=1)], "solo puede tener nivel 'lectura'")
    rechaza(tmp_path, [entrada_base(tipo="accion", nivel="lectura")], "debe tener nivel 'accion' o 'mutante'")
    rechaza(tmp_path, [entrada_base(tipo="comprobacion")], "exige 'severidad' y 'peso'")
    rechaza(tmp_path, [entrada_base(requisitos={"privilegios": "root"})], "incoherentes")
    rechaza(tmp_path, [entrada_base(plataforma={"so": "linux"})], "solo aplica a so: windows")
    rechaza(tmp_path, [entrada_base(plataforma={"so": "windows", "familias": ["debian"]})], "solo aplica a so: linux")
    rechaza(tmp_path, [entrada_base(plataforma={"so": "windows", "build_min": 22631, "build_max": 22000})], "build_min")


@pytest.mark.parametrize("timeout", [0, -1, 86401, "30", True, 1.5])
def test_rechaza_timeout_invalido(tmp_path, timeout):
    rechaza(tmp_path, [entrada_base(timeout_s=timeout)], "timeout_s")


def test_rechaza_tipo_no_permitido_en_el_fichero(tmp_path):
    escribir(tmp_path, [entrada_base()])
    escribir(tmp_path, [entrada_base(id="win_a")], "windows/a.yaml")  # herramienta dentro de windows/
    with pytest.raises(CatalogoError, match="tipo 'herramienta' no permitido"):
        catalogo.cargar_catalogo(tmp_path)


def test_rechaza_comprobacion_en_herramientas_llm(tmp_path):
    rechaza(tmp_path, [entrada_base(tipo="comprobacion", severidad="baja", peso=1)], "no permitido en este fichero")


def test_rechaza_prefijo_o_so_incoherente_con_la_carpeta(tmp_path):
    escribir(tmp_path, [entrada_base()])
    comp = {"tipo": "comprobacion", "severidad": "baja", "peso": 1}
    escribir(tmp_path, [entrada_base(id="lnx_mal", **comp)], "windows/a.yaml")
    with pytest.raises(CatalogoError, match="debe empezar por"):
        catalogo.cargar_catalogo(tmp_path)
    escribir(tmp_path, [entrada_base(id="win_a", **comp)], "windows/a.yaml")
    escribir(tmp_path, [entrada_base(id="lnx_a", **comp)], "linux/a.yaml")  # so: windows en carpeta linux
    with pytest.raises(CatalogoError, match="'plataforma.so' debe ser 'linux'"):
        catalogo.cargar_catalogo(tmp_path)


def test_rechaza_extension_yml(tmp_path):
    escribir(tmp_path, [entrada_base()])
    (tmp_path / "windows").mkdir()
    (tmp_path / "windows" / "a.yml").write_text("version: 1\nentradas: []\n", encoding="utf-8")
    with pytest.raises(CatalogoError, match=".yaml"):
        catalogo.cargar_catalogo(tmp_path)


def test_el_mensaje_de_error_identifica_fichero_y_entrada(tmp_path):
    mensaje = rechaza(tmp_path, [entrada_base(), entrada_base(id="segunda", nivel="otro")], "herramientas_llm.yaml", "'segunda'")
    assert "get_prueba" not in mensaje


# --- Lista de denegación -----------------------------------------------------------------
def _texto_con_token(token: str) -> str:
    return token.replace("*", "Path")


@pytest.mark.parametrize("token", catalogo.LISTA_DENEGACION)
def test_lista_de_denegacion_rechaza_cada_token_en_plantillas(tmp_path, token):
    plantilla = f"Get-Date; {_texto_con_token(token)} -x"
    rechaza(tmp_path, [entrada_base(plantilla=plantilla)], "token denegado", f"'{token}'")


@pytest.mark.parametrize("token", catalogo.LISTA_DENEGACION)
def test_lista_de_denegacion_rechaza_cada_token_en_argv(tmp_path, token):
    argv = ["/usr/bin/true", *_texto_con_token(token).split()]
    entrada = entrada_base(
        id="lnx_prueba", motor="comando", plantilla=QUITAR, argv=argv, plataforma={"so": "linux"},
        requisitos={"privilegios": "usuario"},
    )  # fmt: skip
    escribir(tmp_path, [entrada_base()])
    escribir(tmp_path, [{**entrada, "tipo": "comprobacion", "severidad": "baja", "peso": 1}], "linux/p.yaml")
    with pytest.raises(CatalogoError) as excepcion:
        catalogo.cargar_catalogo(tmp_path)
    assert "token denegado" in str(excepcion.value) and f"'{token}'" in str(excepcion.value)


def test_denegacion_ignora_mayusculas_y_espacios():
    assert catalogo.buscar_token_denegado("invoke-expression $x") == "Invoke-Expression"
    assert catalogo.buscar_token_denegado("CMD    /C dir") == "cmd /c"
    assert catalogo.buscar_token_denegado("Set-MpPreference -DisableRealtimeMonitoring   $True") is not None


def test_denegacion_respeta_limites_de_palabra():
    for inocuo in ("Select-Object Summary, Substring", "Get-Suma", "bash", "pseudo", "Get-Disk", "Start-MpScan", "cmd /cx"):
        assert catalogo.buscar_token_denegado(inocuo) is None, inocuo


def test_denegacion_cubre_la_expansion_de_parametros(tmp_path):
    entrada = entrada_base(plantilla="Get-Item su{sufijo}", parametros={"sufijo": ["ma", "do"]})
    rechaza(tmp_path, [entrada], "'sudo'")


def test_denegacion_cubre_los_valores_de_los_enums(tmp_path):
    entrada = entrada_base(plantilla="Get-Item {x}", parametros={"x": ["Normal", "IEX"]})
    rechaza(tmp_path, [entrada], "'IEX'")


def test_las_25_plantillas_reales_no_contienen_tokens_denegados():
    for entrada in catalogo.cargar_catalogo().entradas.values():
        assert catalogo.buscar_token_denegado(entrada.plantilla or "") is None, entrada.id


# --- Fusión con mapeo_marcos.csv ---------------------------------------------------------
CABECERA = ",".join(catalogo.CAMPOS_CSV)


def csv_marcos(raiz: Path, *filas: str, cabecera: str = CABECERA) -> None:
    (raiz / "mapeo_marcos.csv").write_text("\n".join([cabecera, *filas]) + "\n", encoding="utf-8")


def test_csv_vacio_deja_las_entradas_sin_marcos(tmp_path):
    escribir(tmp_path, [entrada_base()])
    csv_marcos(tmp_path)
    assert catalogo.cargar_catalogo(tmp_path).entradas["get_prueba"].marcos == catalogo.Marcos()


def test_csv_con_verificado_por_se_fusiona_como_verificado(tmp_path):
    escribir(tmp_path, [entrada_base()])
    csv_marcos(tmp_path, "get_prueba,Bench X,1.2.3,Titulo breve,4.1; 4.8,op.acc.1,T1562;T1089,D3-X,mp.s.1,Juan,2026-10-23")
    marcos = catalogo.cargar_catalogo(tmp_path).entradas["get_prueba"].marcos
    assert marcos.verificado is True
    assert marcos.verificado_por == "Juan" and marcos.fecha == "2026-10-23"
    assert marcos.cis_benchmark == "Bench X" and marcos.cis_id == "1.2.3" and marcos.cis_titulo_breve == "Titulo breve"
    assert marcos.cis_controls == ("4.1", "4.8") and marcos.attack == ("T1562", "T1089")
    assert marcos.ccn == ("op.acc.1",) and marcos.d3fend == ("D3-X",) and marcos.ens == ("mp.s.1",)


def test_mapeo_sin_verificado_por_queda_como_no_verificado(tmp_path):
    escribir(tmp_path, [entrada_base()])
    csv_marcos(tmp_path, "get_prueba,Bench X,1.2.3,Titulo,4.1,,T1562,,,,")
    marcos = catalogo.cargar_catalogo(tmp_path).entradas["get_prueba"].marcos
    assert marcos.verificado is False and marcos.verificado_por is None
    assert marcos.cis_id == "1.2.3" and marcos.attack == ("T1562",)


def test_verificado_por_en_blanco_cuenta_como_ausente(tmp_path):
    escribir(tmp_path, [entrada_base()])
    csv_marcos(tmp_path, "get_prueba,,,,,,T1562,,,   ,2026-10-23")
    assert catalogo.cargar_catalogo(tmp_path).entradas["get_prueba"].marcos.verificado is False


def test_csv_rechaza_id_inexistente_con_numero_de_linea(tmp_path):
    escribir(tmp_path, [entrada_base()])
    csv_marcos(tmp_path, "no_existe,,,,,,,,,Juan,2026-10-23")
    with pytest.raises(CatalogoError, match=r"mapeo_marcos.csv:2: .*no_existe"):
        catalogo.cargar_catalogo(tmp_path)


def test_csv_rechaza_id_duplicado(tmp_path):
    escribir(tmp_path, [entrada_base()])
    csv_marcos(tmp_path, "get_prueba,,,,,,T1,,,,", "get_prueba,,,,,,T2,,,,")
    with pytest.raises(CatalogoError, match="id duplicado"):
        catalogo.cargar_catalogo(tmp_path)


def test_csv_rechaza_cabecera_incorrecta(tmp_path):
    escribir(tmp_path, [entrada_base()])
    csv_marcos(tmp_path, cabecera="id,cis_id")
    with pytest.raises(CatalogoError, match="cabecera"):
        catalogo.cargar_catalogo(tmp_path)


def test_csv_rechaza_fecha_mal_formada_y_filas_con_columnas_de_mas(tmp_path):
    escribir(tmp_path, [entrada_base()])
    csv_marcos(tmp_path, "get_prueba,,,,,,,,,Juan,23/10/2026")
    with pytest.raises(CatalogoError, match="AAAA-MM-DD"):
        catalogo.cargar_catalogo(tmp_path)
    csv_marcos(tmp_path, "get_prueba,,,,,,,,,Juan,2026-10-23,sobra")
    with pytest.raises(CatalogoError, match="columnas"):
        catalogo.cargar_catalogo(tmp_path)


def test_yaml_no_puede_afirmar_verificado_true(tmp_path):
    rechaza(tmp_path, [entrada_base(marcos={"verificado": True, "attack": ["T1"]})], "verificado: true", "mapeo_marcos.csv")


def test_marcos_en_yaml_quedan_no_verificados_y_no_se_duplican_en_el_csv(tmp_path):
    escribir(tmp_path, [entrada_base(marcos={"cis": {"id": "9.9"}, "attack": ["T1"], "verificado": False})])
    marcos = catalogo.cargar_catalogo(tmp_path).entradas["get_prueba"].marcos
    assert marcos.cis_id == "9.9" and marcos.attack == ("T1",) and marcos.verificado is False
    csv_marcos(tmp_path, "get_prueba,,,,,,T2,,,Juan,2026-10-23")
    with pytest.raises(CatalogoError, match="una sola fuente"):
        catalogo.cargar_catalogo(tmp_path)


def test_marcos_rechaza_campos_desconocidos(tmp_path):
    rechaza(tmp_path, [entrada_base(marcos={"nist": ["x"]})], "campo desconocido 'nist'")


def test_el_csv_real_no_contiene_identificadores_sin_verificar_ni_verificados_sin_firma():
    """Regla 15: ningún mapeo del catálogo real es verificado sin verificado_por."""
    for entrada in catalogo.cargar_catalogo().entradas.values():
        assert entrada.marcos.verificado == bool(entrada.marcos.verificado_por), entrada.id
