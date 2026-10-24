"""Cargador estricto del catálogo YAML: única fuente de verdad de herramientas y comprobaciones.

El catálogo (carpeta `catalogo/`) sustituye a la WHITELIST escrita en código. Este módulo lo
lee, lo valida y devuelve entradas inmutables; no ejecuta nada. Ante cualquier irregularidad
(campo desconocido, id duplicado, enum inválido, marcador sin declarar, token de la lista de
denegación) lanza `CatalogoError` indicando el fichero y la entrada. Un catálogo que no
valida impide arrancar: la capa ejecutora nunca trabaja con un catálogo a medias.
"""

from __future__ import annotations

import csv
import itertools
import re
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path
from string import Formatter
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:  # solo para anotar tipos: src.plataforma importa este módulo, no al revés
    from src.plataforma.deteccion import Capacidades

RAIZ_CATALOGO = Path(__file__).resolve().parent.parent / "catalogo"

VERSION_ESQUEMA = 1

# --- Valores permitidos (ver catalogo/_ESQUEMA.md) ---------------------------------------
TIPOS = ("herramienta", "comprobacion", "accion")
NIVELES = ("lectura", "accion", "mutante")
RIESGOS = ("bajo", "alto")
SENSIBILIDADES = ("tecnica", "personal")
PERFILES = ("hogar", "sistemas")
PERFIL_POR_DEFECTO = "hogar"
SISTEMAS = ("windows", "linux")
FAMILIAS = ("debian", "rhel", "arch", "suse")
PRIVILEGIOS = ("usuario", "admin", "root")
MOTORES = ("powershell", "registro", "comando", "python")
AREAS = ("cuentas", "red", "defender", "dispositivo", "sistema", "actualizaciones", "malware")
SEVERIDADES = ("alta", "media", "baja")
HIVES = ("HKLM", "HKCU", "HKCR", "HKU", "HKCC")

PATRON_ID = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
PATRON_PARAMETRO = re.compile(r"^[a-z_][a-z0-9_]{0,63}$")
# Los valores de un enum acaban dentro de un comando: solo caracteres inertes y sin guion inicial.
PATRON_VALOR_ENUM = re.compile(r"^[A-Za-z0-9_.][A-Za-z0-9_.-]{0,63}$")
PATRON_BINARIO = re.compile(r"^[A-Za-z0-9._+-]{1,64}$")
PATRON_EDICION = re.compile(r"^[A-Za-z0-9 ._-]{1,64}$")
_MARCADOR_SUELTO = re.compile(r"\{[A-Za-z_]\w*\}")

TIMEOUT_POR_DEFECTO_S = 30
TIMEOUT_MAXIMO_S = 86400
MAX_COMBINACIONES = 5000

# --- Lista de denegación (revisable) -----------------------------------------------------
# Ninguna plantilla ni argv del catálogo puede contener estos tokens. La comparación ignora
# mayúsculas, tolera espacios variables y respeta límites de palabra (`su` no casa con `Suma`).
# El `*` final equivale a «cualquier continuación» (p. ej. `-ExclusionPath`).
LISTA_DENEGACION: tuple[str, ...] = (
    "-DownloadFile",
    "-DisableRealtimeMonitoring $true",
    "-DisableIOAVProtection $true",
    "Set-MpPreference -Exclusion*",
    "Add-MpPreference -Exclusion*",
    "HailMary",
    "Invoke-Expression",
    "IEX",
    "DownloadString",
    "Start-Process",
    "cmd /c",
    "bash -c",
    "sh -c",
    "sudo",
    "su",
    "pkexec",
    "doas",
    "rm -rf",
    "Remove-Item -Recurse",
    "Format-Volume",
    "Clear-Disk",
    "bcdedit",
    "vssadmin delete",
    "wevtutil cl",
)

CAMPOS_CSV = (
    "id",
    "cis_benchmark",
    "cis_id",
    "cis_titulo_breve",
    "cis_controls",
    "ccn",
    "attack",
    "d3fend",
    "ens",
    "verificado_por",
    "fecha",
)


class CatalogoError(ValueError):
    """El catálogo no cumple el esquema; el mensaje indica fichero y entrada."""


# --- Modelo de datos ---------------------------------------------------------------------
@dataclass(frozen=True)
class Plataforma:
    """Dónde aplica una entrada: sistema operativo y, opcionalmente, familia/build/edición."""

    so: str
    familias: tuple[str, ...] | None = None
    build_min: int | None = None
    build_max: int | None = None
    ediciones: tuple[str, ...] | None = None


@dataclass(frozen=True)
class Requisitos:
    """Privilegios y binarios que necesita la entrada para poder ejecutarse."""

    privilegios: str
    binarios: tuple[str, ...] = ()


@dataclass(frozen=True)
class ClaveRegistro:
    """Valor del registro de Windows que se lee (solo lectura, vía winreg)."""

    hive: str
    ruta: str
    valor: str


@dataclass(frozen=True)
class Marcos:
    """Mapeos a marcos normativos. `verificado` solo es True si consta `verificado_por`."""

    cis_benchmark: str | None = None
    cis_id: str | None = None
    cis_titulo_breve: str | None = None
    cis_controls: tuple[str, ...] = ()
    ccn: tuple[str, ...] = ()
    attack: tuple[str, ...] = ()
    d3fend: tuple[str, ...] = ()
    ens: tuple[str, ...] = ()
    verificado: bool = False
    verificado_por: str | None = None
    fecha: str | None = None

    def tiene_datos(self) -> bool:
        """Indica si hay algún identificador de marco informado."""
        return any(
            (
                self.cis_benchmark,
                self.cis_id,
                self.cis_titulo_breve,
                self.cis_controls,
                self.ccn,
                self.attack,
                self.d3fend,
                self.ens,
            )
        )


@dataclass(frozen=True)
class Entrada:
    """Una herramienta, comprobación o acción del catálogo, ya validada."""

    id: str
    titulo: str
    descripcion_llm: str
    justificacion: str
    tipo: str
    nivel: str
    riesgo: str
    sensibilidad: str
    perfiles: tuple[str, ...]
    plataforma: Plataforma
    requisitos: Requisitos
    motor: str
    area: str
    plantilla: str | None = None
    argv: tuple[str, ...] | None = None
    clave_registro: ClaveRegistro | None = None
    parametros: dict[str, tuple[str, ...]] = field(default_factory=dict)
    severidad: str | None = None
    peso: int | None = None
    marcos: Marcos = field(default_factory=Marcos)
    timeout_s: int = TIMEOUT_POR_DEFECTO_S
    origen: str = ""


@dataclass(frozen=True)
class Catalogo:
    """Conjunto de entradas cargadas, indexadas por id y en orden de aparición."""

    entradas: dict[str, Entrada]

    def herramientas_llm(self) -> dict[str, Entrada]:
        """Entradas de tipo `herramienta`: las únicas que se exponen una a una al LLM."""
        return {i: e for i, e in self.entradas.items() if e.tipo == "herramienta"}


# --- Lista de denegación -----------------------------------------------------------------
def _patron_token(token: str) -> re.Pattern[str]:
    """Convierte un token de la lista de denegación en una expresión regular."""
    cuerpo = r"\s+".join(re.escape(parte).replace(r"\*", r"\S*") for parte in token.split())
    inicio = r"(?<![\w-])" if re.match(r"\w", token[0]) else ""
    fin = r"(?![\w-])" if re.match(r"\w", token[-1]) else ""
    return re.compile(inicio + cuerpo + fin, re.IGNORECASE)


def buscar_token_denegado(texto: str) -> str | None:
    """Devuelve el primer token de LISTA_DENEGACION presente en `texto`, o None."""
    for token in LISTA_DENEGACION:
        if _patron_token(token).search(texto):
            return token
    return None


# --- Lectura de YAML ---------------------------------------------------------------------
class _CargadorEstricto(yaml.SafeLoader):
    """SafeLoader que rechaza claves duplicadas (PyYAML se queda en silencio con la última)."""


def _construir_mapa_sin_duplicados(loader: _CargadorEstricto, nodo: yaml.MappingNode, deep: bool = False) -> Any:
    vistas: set[Any] = set()
    for nodo_clave, _ in nodo.value:
        clave = loader.construct_object(nodo_clave, deep=deep)
        if clave in vistas:
            raise yaml.constructor.ConstructorError(
                None, None, f"clave duplicada: {clave!r}", nodo_clave.start_mark
            )
        vistas.add(clave)
    return loader.construct_mapping(nodo, deep)


_CargadorEstricto.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construir_mapa_sin_duplicados
)


def _leer_yaml(ruta: Path) -> Any:
    try:
        with ruta.open(encoding="utf-8") as fichero:
            return yaml.load(fichero, Loader=_CargadorEstricto)  # noqa: S506 (SafeLoader)
    except yaml.YAMLError as error:
        raise CatalogoError(f"{ruta.name}: YAML inválido: {error}") from error
    except OSError as error:
        raise CatalogoError(f"{ruta.name}: no se puede leer el fichero: {error}") from error


# --- Validación de campos ----------------------------------------------------------------
class _Contexto:
    """Dónde estamos validando: sirve solo para construir mensajes de error precisos."""

    def __init__(self, fichero: str, entrada: str) -> None:
        self.fichero = fichero
        self.entrada = entrada

    def error(self, mensaje: str) -> CatalogoError:
        return CatalogoError(f"{self.fichero}: entrada '{self.entrada}': {mensaje}")


def _exigir_dict(valor: Any, ctx: _Contexto, nombre: str) -> dict[str, Any]:
    if not isinstance(valor, dict):
        raise ctx.error(f"'{nombre}' debe ser un mapa.")
    return valor


def _exigir_claves(
    dato: dict[str, Any], ctx: _Contexto, nombre: str, obligatorias: tuple[str, ...], opcionales: tuple[str, ...] = ()
) -> None:
    """Rechaza campos desconocidos y exige los obligatorios."""
    for clave in dato:
        if clave not in obligatorias and clave not in opcionales:
            raise ctx.error(f"campo desconocido '{clave}' en '{nombre}'.")
    for clave in obligatorias:
        if clave not in dato:
            raise ctx.error(f"falta el campo obligatorio '{clave}' en '{nombre}'.")


def _texto(valor: Any, ctx: _Contexto, nombre: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        raise ctx.error(f"'{nombre}' debe ser un texto no vacío.")
    return valor


def _enum(valor: Any, ctx: _Contexto, nombre: str, permitidos: tuple[str, ...]) -> str:
    if not isinstance(valor, str) or valor not in permitidos:
        raise ctx.error(f"valor inválido en '{nombre}': {valor!r} (permitidos: {list(permitidos)}).")
    return valor


def _entero(valor: Any, ctx: _Contexto, nombre: str, minimo: int, maximo: int) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int) or not minimo <= valor <= maximo:
        raise ctx.error(f"'{nombre}' debe ser un entero entre {minimo} y {maximo}.")
    return valor


def _lista_textos(valor: Any, ctx: _Contexto, nombre: str, *, patron: re.Pattern[str] | None = None) -> tuple[str, ...]:
    if not isinstance(valor, list):
        raise ctx.error(f"'{nombre}' debe ser una lista.")
    for elemento in valor:
        if not isinstance(elemento, str) or not elemento.strip():
            raise ctx.error(f"'{nombre}' solo admite textos no vacíos (¿falta comillar un True/False?): {elemento!r}.")
        if patron is not None and not patron.match(elemento):
            raise ctx.error(f"valor no permitido en '{nombre}': {elemento!r}.")
    return tuple(valor)


def _lista_enum(valor: Any, ctx: _Contexto, nombre: str, permitidos: tuple[str, ...]) -> tuple[str, ...]:
    elementos = _lista_textos(valor, ctx, nombre)
    if not elementos:
        raise ctx.error(f"'{nombre}' no puede estar vacía.")
    if len(set(elementos)) != len(elementos):
        raise ctx.error(f"'{nombre}' tiene valores repetidos.")
    for elemento in elementos:
        _enum(elemento, ctx, nombre, permitidos)
    return elementos


def _parsear_plataforma(valor: Any, ctx: _Contexto) -> Plataforma:
    dato = _exigir_dict(valor, ctx, "plataforma")
    _exigir_claves(dato, ctx, "plataforma", ("so",), ("familias", "build_min", "build_max", "ediciones"))
    so = _enum(dato["so"], ctx, "plataforma.so", SISTEMAS)
    familias = ediciones = None
    if dato.get("familias") is not None:
        if so != "linux":
            raise ctx.error("'plataforma.familias' solo aplica a so: linux.")
        familias = _lista_enum(dato["familias"], ctx, "plataforma.familias", FAMILIAS)
    if dato.get("ediciones") is not None:
        if so != "windows":
            raise ctx.error("'plataforma.ediciones' solo aplica a so: windows.")
        ediciones = _lista_textos(dato["ediciones"], ctx, "plataforma.ediciones", patron=PATRON_EDICION)
        if not ediciones:
            raise ctx.error("'plataforma.ediciones' no puede estar vacía (usa null para «todas»).")
    builds: dict[str, int | None] = {}
    for nombre in ("build_min", "build_max"):
        builds[nombre] = None
        if dato.get(nombre) is not None:
            if so != "windows":
                raise ctx.error(f"'plataforma.{nombre}' solo aplica a so: windows.")
            builds[nombre] = _entero(dato[nombre], ctx, f"plataforma.{nombre}", 1, 10**6)
    build_min, build_max = builds["build_min"], builds["build_max"]
    if build_min is not None and build_max is not None and build_min > build_max:
        raise ctx.error("'plataforma.build_min' no puede ser mayor que 'plataforma.build_max'.")
    return Plataforma(so=so, familias=familias, build_min=build_min, build_max=build_max, ediciones=ediciones)


def _parsear_requisitos(valor: Any, ctx: _Contexto, so: str) -> Requisitos:
    dato = _exigir_dict(valor, ctx, "requisitos")
    _exigir_claves(dato, ctx, "requisitos", ("privilegios",), ("binarios",))
    privilegios = _enum(dato["privilegios"], ctx, "requisitos.privilegios", PRIVILEGIOS)
    if (so == "windows" and privilegios == "root") or (so == "linux" and privilegios == "admin"):
        raise ctx.error(f"privilegios '{privilegios}' incoherentes con so '{so}'.")
    binarios = _lista_textos(dato.get("binarios", []), ctx, "requisitos.binarios", patron=PATRON_BINARIO)
    return Requisitos(privilegios=privilegios, binarios=binarios)


def _parsear_clave_registro(valor: Any, ctx: _Contexto) -> ClaveRegistro:
    dato = _exigir_dict(valor, ctx, "clave_registro")
    _exigir_claves(dato, ctx, "clave_registro", ("hive", "ruta", "valor"))
    return ClaveRegistro(
        hive=_enum(dato["hive"], ctx, "clave_registro.hive", HIVES),
        ruta=_texto(dato["ruta"], ctx, "clave_registro.ruta"),
        valor=_texto(dato["valor"], ctx, "clave_registro.valor"),
    )


def _parsear_parametros(valor: Any, ctx: _Contexto) -> dict[str, tuple[str, ...]]:
    dato = _exigir_dict(valor, ctx, "parametros")
    parametros: dict[str, tuple[str, ...]] = {}
    for nombre, valores in dato.items():
        if not isinstance(nombre, str) or not PATRON_PARAMETRO.match(nombre):
            raise ctx.error(f"nombre de parámetro inválido: {nombre!r}.")
        enum = _lista_textos(valores, ctx, f"parametros.{nombre}", patron=PATRON_VALOR_ENUM)
        if not enum:
            raise ctx.error(f"'parametros.{nombre}' no puede estar vacío.")
        if len(set(enum)) != len(enum):
            raise ctx.error(f"'parametros.{nombre}' tiene valores repetidos.")
        for elemento in enum:
            if (token := buscar_token_denegado(elemento)) is not None:
                raise ctx.error(f"el valor {elemento!r} de 'parametros.{nombre}' contiene el token denegado '{token}'.")
        parametros[nombre] = enum
    return parametros


def _marcadores_usados(texto: str, parametros: dict[str, tuple[str, ...]], ctx: _Contexto, nombre: str) -> set[str]:
    """Comprueba los marcadores `{x}` de un texto y devuelve los parámetros que usa.

    Sin parámetros, el texto se usa tal cual (las llaves de PowerShell son literales) y solo se
    rechaza lo que parece un marcador (`{nombre}`). Con parámetros, el texto pasa por
    `str.format`: toda llave es marcador declarado o está duplicada (`{{`, `}}`).
    """
    if not parametros:
        if (suelto := _MARCADOR_SUELTO.search(texto)) is not None:
            raise ctx.error(f"marcador {suelto.group()} en '{nombre}' sin declarar en 'parametros'.")
        return set()
    try:
        trozos = list(Formatter().parse(texto))
    except ValueError as error:
        raise ctx.error(f"'{nombre}' mal formada para str.format: {error}") from error
    usados: set[str] = set()
    for _literal, campo, formato, conversion in trozos:
        if campo is None:
            continue
        if formato or conversion:
            raise ctx.error(f"marcador {{{campo}}} en '{nombre}' con formato o conversión: no permitido.")
        if campo not in parametros:
            raise ctx.error(f"marcador {{{campo}}} en '{nombre}' sin declarar en 'parametros'.")
        usados.add(campo)
    return usados


def _renderizar(texto: str, parametros: dict[str, tuple[str, ...]], valores: dict[str, str]) -> str:
    return texto.format(**valores) if parametros else texto


def _comprobar_denegacion(textos: tuple[str, ...], parametros: dict[str, tuple[str, ...]], ctx: _Contexto, nombre: str) -> None:
    """Aplica la lista de denegación a la plantilla/argv y a todas sus expansiones posibles."""
    combinaciones = 1
    for valores in parametros.values():
        combinaciones *= len(valores)
    if combinaciones > MAX_COMBINACIONES:
        raise ctx.error(f"demasiadas combinaciones de parámetros ({combinaciones}) para validar '{nombre}'.")
    nombres = list(parametros)
    for combinacion in itertools.product(*(parametros[n] for n in nombres)):
        valores = dict(zip(nombres, combinacion))
        expandidos = [_renderizar(t, parametros, valores) for t in textos]
        for candidato in (*expandidos, " ".join(expandidos)):
            if (token := buscar_token_denegado(candidato)) is not None:
                raise ctx.error(f"'{nombre}' contiene el token denegado '{token}'.")


def _parsear_marcos(valor: Any, ctx: _Contexto) -> Marcos:
    if valor is None:
        return Marcos()
    dato = _exigir_dict(valor, ctx, "marcos")
    _exigir_claves(dato, ctx, "marcos", (), ("cis", "cis_controls", "ccn", "attack", "d3fend", "ens", "verificado"))
    if dato.get("verificado") not in (None, False):
        raise ctx.error(
            "'marcos.verificado: true' no se admite en el YAML: la verificación debe constar en "
            "mapeo_marcos.csv (columna verificado_por)."
        )
    cis = _exigir_dict(dato.get("cis", {}), ctx, "marcos.cis")
    _exigir_claves(cis, ctx, "marcos.cis", (), ("benchmark", "id", "titulo_breve"))
    return Marcos(
        cis_benchmark=cis.get("benchmark"),
        cis_id=cis.get("id"),
        cis_titulo_breve=cis.get("titulo_breve"),
        cis_controls=_lista_textos(dato.get("cis_controls", []), ctx, "marcos.cis_controls"),
        ccn=_lista_textos(dato.get("ccn", []), ctx, "marcos.ccn"),
        attack=_lista_textos(dato.get("attack", []), ctx, "marcos.attack"),
        d3fend=_lista_textos(dato.get("d3fend", []), ctx, "marcos.d3fend"),
        ens=_lista_textos(dato.get("ens", []), ctx, "marcos.ens"),
    )


CAMPOS_OBLIGATORIOS = (
    "id", "titulo", "descripcion_llm", "justificacion", "tipo", "nivel", "riesgo", "sensibilidad",
    "perfiles", "plataforma", "requisitos", "motor", "area",
)  # fmt: skip
CAMPOS_OPCIONALES = (
    "plantilla", "argv", "clave_registro", "parametros", "severidad", "peso", "marcos", "timeout_s",
)  # fmt: skip


def _parsear_entrada(dato: Any, fichero: str, indice: int) -> Entrada:
    """Valida un elemento de `entradas` y lo convierte en `Entrada`."""
    etiqueta = dato["id"] if isinstance(dato, dict) and isinstance(dato.get("id"), str) else f"#{indice}"
    ctx = _Contexto(fichero, etiqueta)
    dato = _exigir_dict(dato, ctx, "entrada")
    _exigir_claves(dato, ctx, "entrada", CAMPOS_OBLIGATORIOS, CAMPOS_OPCIONALES)

    id_ = _texto(dato["id"], ctx, "id")
    if not PATRON_ID.match(id_):
        raise ctx.error("id inválido: debe cumplir ^[a-zA-Z0-9_-]{1,64}$.")
    tipo = _enum(dato["tipo"], ctx, "tipo", TIPOS)
    nivel = _enum(dato["nivel"], ctx, "nivel", NIVELES)
    motor = _enum(dato["motor"], ctx, "motor", MOTORES)
    plataforma = _parsear_plataforma(dato["plataforma"], ctx)
    requisitos = _parsear_requisitos(dato["requisitos"], ctx, plataforma.so)

    if tipo == "comprobacion" and nivel != "lectura":
        raise ctx.error("una 'comprobacion' solo puede tener nivel 'lectura'.")
    if tipo == "accion" and nivel == "lectura":
        raise ctx.error("una 'accion' debe tener nivel 'accion' o 'mutante'.")
    if motor == "registro" and nivel != "lectura":
        raise ctx.error("el motor 'registro' es de solo lectura (nivel 'lectura').")
    if motor in ("powershell", "registro") and plataforma.so != "windows":
        raise ctx.error(f"el motor '{motor}' solo aplica a so: windows.")

    severidad = peso = None
    if "severidad" in dato:
        severidad = _enum(dato["severidad"], ctx, "severidad", SEVERIDADES)
    if "peso" in dato:
        peso = _entero(dato["peso"], ctx, "peso", 0, 1000)
    if tipo == "comprobacion" and (severidad is None or peso is None):
        raise ctx.error("una 'comprobacion' exige 'severidad' y 'peso'.")

    parametros = _parsear_parametros(dato["parametros"], ctx) if "parametros" in dato else {}
    plantilla = argv = clave_registro = None
    if motor == "powershell":
        _prohibir(dato, ctx, motor, ("argv", "clave_registro"))
        plantilla = _texto(dato.get("plantilla"), ctx, "plantilla")
        usados = _marcadores_usados(plantilla, parametros, ctx, "plantilla")
        textos = (plantilla,)
    elif motor == "comando":
        _prohibir(dato, ctx, motor, ("plantilla", "clave_registro"))
        argv = _lista_textos(dato.get("argv"), ctx, "argv")
        if not argv:
            raise ctx.error("'argv' no puede estar vacío.")
        usados = set().union(*(_marcadores_usados(a, parametros, ctx, "argv") for a in argv))
        textos = argv
    elif motor == "registro":
        _prohibir(dato, ctx, motor, ("plantilla", "argv", "parametros"))
        clave_registro = _parsear_clave_registro(dato.get("clave_registro"), ctx)
        usados, textos = set(), ()
    else:  # python: la lógica vive en una función registrada con el id de la entrada
        _prohibir(dato, ctx, motor, ("plantilla", "argv", "clave_registro", "parametros"))
        usados, textos = set(), ()
    sin_usar = set(parametros) - usados
    if sin_usar:
        raise ctx.error(f"parámetro(s) declarado(s) pero no usados en la plantilla/argv: {sorted(sin_usar)}.")
    if textos:
        _comprobar_denegacion(textos, parametros, ctx, "plantilla" if plantilla is not None else "argv")

    return Entrada(
        id=id_,
        titulo=_texto(dato["titulo"], ctx, "titulo"),
        descripcion_llm=_texto(dato["descripcion_llm"], ctx, "descripcion_llm"),
        justificacion=_texto(dato["justificacion"], ctx, "justificacion"),
        tipo=tipo,
        nivel=nivel,
        riesgo=_enum(dato["riesgo"], ctx, "riesgo", RIESGOS),
        sensibilidad=_enum(dato["sensibilidad"], ctx, "sensibilidad", SENSIBILIDADES),
        perfiles=_lista_enum(dato["perfiles"], ctx, "perfiles", PERFILES),
        plataforma=plataforma,
        requisitos=requisitos,
        motor=motor,
        area=_enum(dato["area"], ctx, "area", AREAS),
        plantilla=plantilla,
        argv=argv,
        clave_registro=clave_registro,
        parametros=parametros,
        severidad=severidad,
        peso=peso,
        marcos=_parsear_marcos(dato.get("marcos"), ctx),
        timeout_s=_entero(dato.get("timeout_s", TIMEOUT_POR_DEFECTO_S), ctx, "timeout_s", 1, TIMEOUT_MAXIMO_S),
        origen=fichero,
    )


def _prohibir(dato: dict[str, Any], ctx: _Contexto, motor: str, campos: tuple[str, ...]) -> None:
    for campo in campos:
        if campo in dato:
            raise ctx.error(f"el campo '{campo}' no es válido con motor '{motor}'.")


# --- Ficheros y carpeta ------------------------------------------------------------------
def _cargar_fichero(ruta: Path, nombre: str, tipos_permitidos: tuple[str, ...], so_carpeta: str | None) -> list[Entrada]:
    """Carga un YAML del catálogo comprobando la cabecera y la coherencia con su carpeta."""
    contenido = _leer_yaml(ruta)
    if not isinstance(contenido, dict):
        raise CatalogoError(f"{nombre}: el fichero debe ser un mapa con 'version' y 'entradas'.")
    for clave in contenido:
        if clave not in ("version", "entradas"):
            raise CatalogoError(f"{nombre}: campo desconocido '{clave}' en la cabecera.")
    if contenido.get("version") != VERSION_ESQUEMA:
        raise CatalogoError(f"{nombre}: 'version' debe ser {VERSION_ESQUEMA}.")
    elementos = contenido.get("entradas")
    if not isinstance(elementos, list):
        raise CatalogoError(f"{nombre}: 'entradas' debe ser una lista.")

    entradas = [_parsear_entrada(e, nombre, i) for i, e in enumerate(elementos, start=1)]
    for entrada in entradas:
        ctx = _Contexto(nombre, entrada.id)
        if entrada.tipo not in tipos_permitidos:
            raise ctx.error(f"tipo '{entrada.tipo}' no permitido en este fichero (permitidos: {list(tipos_permitidos)}).")
        if so_carpeta is not None:
            prefijos = ("win_", "comun_") if so_carpeta == "windows" else ("lnx_", "comun_")
            if entrada.plataforma.so != so_carpeta:
                raise ctx.error(f"'plataforma.so' debe ser '{so_carpeta}' en esta carpeta.")
            if not entrada.id.startswith(prefijos):
                raise ctx.error(f"el id debe empezar por uno de {list(prefijos)}.")
    return entradas


def _leer_csv_marcos(ruta: Path) -> dict[str, tuple[int, dict[str, str]]]:
    """Lee mapeo_marcos.csv y devuelve {id: (línea, fila)}. Un CSV ausente equivale a vacío."""
    if not ruta.exists():
        return {}
    filas: dict[str, tuple[int, dict[str, str]]] = {}
    with ruta.open(encoding="utf-8-sig", newline="") as fichero:
        lector = csv.DictReader(fichero)
        if tuple(lector.fieldnames or ()) != CAMPOS_CSV:
            raise CatalogoError(f"{ruta.name}: la cabecera debe ser exactamente: {','.join(CAMPOS_CSV)}.")
        for fila in lector:
            linea = lector.line_num
            if None in fila or None in fila.values():
                raise CatalogoError(f"{ruta.name}:{linea}: número de columnas incorrecto.")
            id_ = fila["id"].strip()
            if id_ in filas:
                raise CatalogoError(f"{ruta.name}:{linea}: id duplicado '{id_}' (primera aparición en la línea {filas[id_][0]}).")
            filas[id_] = (linea, {k: v.strip() for k, v in fila.items()})
    return filas


def _lista_csv(texto: str) -> tuple[str, ...]:
    return tuple(parte.strip() for parte in texto.split(";") if parte.strip())


def _fusionar_marcos(entradas: dict[str, Entrada], ruta: Path) -> dict[str, Entrada]:
    """Fusiona el CSV con las entradas. Sin `verificado_por` el mapeo queda como verificado=False."""
    for id_, (linea, fila) in _leer_csv_marcos(ruta).items():
        if id_ not in entradas:
            raise CatalogoError(f"{ruta.name}:{linea}: el id '{id_}' no existe en el catálogo.")
        entrada = entradas[id_]
        if entrada.marcos.tiene_datos():
            raise CatalogoError(f"{ruta.name}:{linea}: '{id_}' ya tiene 'marcos' en el YAML; usa una sola fuente.")
        fecha = fila["fecha"] or None
        if fecha is not None:
            try:
                date.fromisoformat(fecha)
            except ValueError as error:
                raise CatalogoError(f"{ruta.name}:{linea}: 'fecha' debe ser AAAA-MM-DD: {fecha!r}.") from error
        verificado_por = fila["verificado_por"] or None
        marcos = Marcos(
            cis_benchmark=fila["cis_benchmark"] or None,
            cis_id=fila["cis_id"] or None,
            cis_titulo_breve=fila["cis_titulo_breve"] or None,
            cis_controls=_lista_csv(fila["cis_controls"]),
            ccn=_lista_csv(fila["ccn"]),
            attack=_lista_csv(fila["attack"]),
            d3fend=_lista_csv(fila["d3fend"]),
            ens=_lista_csv(fila["ens"]),
            verificado=verificado_por is not None,
            verificado_por=verificado_por,
            fecha=fecha,
        )
        entradas[id_] = replace(entrada, marcos=marcos)
    return entradas


def cargar_catalogo(raiz: Path | None = None) -> Catalogo:
    """Carga y valida todo el catálogo: herramientas_llm.yaml, windows/, linux/ y mapeo_marcos.csv."""
    raiz = RAIZ_CATALOGO if raiz is None else Path(raiz)
    fichero_llm = raiz / "herramientas_llm.yaml"
    if not fichero_llm.is_file():
        raise CatalogoError(f"No existe {fichero_llm}.")

    entradas: dict[str, Entrada] = {}

    def _registrar(nuevas: list[Entrada]) -> None:
        for entrada in nuevas:
            previa = entradas.get(entrada.id)
            if previa is not None:
                raise CatalogoError(
                    f"{entrada.origen}: entrada '{entrada.id}': id duplicado (ya definido en {previa.origen})."
                )
            entradas[entrada.id] = entrada

    _registrar(_cargar_fichero(fichero_llm, "herramientas_llm.yaml", ("herramienta",), None))
    for so in SISTEMAS:
        carpeta = raiz / so
        if not carpeta.is_dir():
            continue
        for ruta in sorted(carpeta.iterdir()):
            if ruta.suffix == ".yml":
                raise CatalogoError(f"{so}/{ruta.name}: usa la extensión .yaml.")
            if ruta.suffix == ".yaml":
                _registrar(_cargar_fichero(ruta, f"{so}/{ruta.name}", ("comprobacion", "accion"), so))

    return Catalogo(entradas=_fusionar_marcos(entradas, raiz / "mapeo_marcos.csv"))


# --- Aplicabilidad al equipo -------------------------------------------------------------
def aplicable(entrada: Entrada, capacidades: Capacidades, perfil: str) -> tuple[bool, str]:
    """Decide si una entrada aplica a este equipo y perfil; devuelve (aplica, motivo).

    Comprueba, por este orden: sistema operativo, build y edición (Windows), familia (Linux),
    binarios requeridos y perfil. El motivo explica la primera causa de exclusión. Los
    privilegios no excluyen: una entrada que exige administrador o root sigue siendo aplicable
    y se marcará como `requiere_privilegios` al evaluarla.
    """
    if perfil not in PERFILES:
        raise ValueError(f"perfil desconocido: {perfil!r} (permitidos: {list(PERFILES)}).")
    plataforma = entrada.plataforma
    if plataforma.so != capacidades.so:
        return False, f"es de {plataforma.so} y este equipo es {capacidades.so}"

    if plataforma.so == "windows":
        build = capacidades.windows_build
        if plataforma.build_min is not None or plataforma.build_max is not None:
            if build is None:
                return False, "no se pudo determinar el build de Windows"
            if plataforma.build_min is not None and build < plataforma.build_min:
                return False, f"requiere el build {plataforma.build_min} o superior (este equipo: {build})"
            if plataforma.build_max is not None and build > plataforma.build_max:
                return False, f"requiere el build {plataforma.build_max} o inferior (este equipo: {build})"
        if plataforma.ediciones is not None:
            permitidas = {edicion.lower() for edicion in plataforma.ediciones}
            if capacidades.windows_edicion.lower() not in permitidas:
                return False, f"no aplica a la edición {capacidades.windows_edicion or 'desconocida'}"
    elif plataforma.familias is not None and capacidades.familia not in plataforma.familias:
        return False, f"no aplica a la familia {capacidades.familia}"

    for binario in entrada.requisitos.binarios:
        if capacidades.binarios.get(binario) is None:
            return False, f"falta el binario '{binario}'"

    if perfil not in entrada.perfiles:
        return False, f"no está en el perfil '{perfil}'"
    return True, "aplicable"
