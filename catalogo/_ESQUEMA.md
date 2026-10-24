# Esquema del catálogo

El catálogo es la **única fuente de verdad** de las herramientas y comprobaciones de ProtexiumAI (regla 9 de `CLAUDE.md`). Lo lee y valida `src/catalogo.py`; el esquema que ve el LLM (`src/tools_schema.py`) y la WHITELIST del executor (`src/executor.py`) se derivan de él. Si algo no cumple lo descrito aquí, el cargador lanza `CatalogoError` indicando fichero y entrada, y la aplicación no arranca.

## Estructura

```
catalogo/
  _ESQUEMA.md                documentación (este fichero)
  herramientas_llm.yaml      herramientas expuestas al LLM (solo tipo: herramienta)
  mapeo_marcos.csv           mapeos a marcos (CIS, CCN, ATT&CK…); lo rellena Juan
  windows/*.yaml             comprobaciones y acciones de Windows (H2) — ids con prefijo win_ o comun_
  linux/*.yaml               comprobaciones y acciones de Linux (H3) — ids con prefijo lnx_ o comun_
```

Los `.yaml` de `windows/` y `linux/` solo admiten `tipo: comprobacion` o `accion`; `herramientas_llm.yaml` solo admite `tipo: herramienta`. Los ids son únicos en todo el catálogo. Los 25 ids heredados de la WHITELIST no llevan prefijo.

## Cabecera de cada fichero

| Campo | Valor |
|---|---|
| `version` | `1` (obligatorio) |
| `entradas` | lista de entradas (puede estar vacía) |

Cualquier otra clave en la cabecera, o una clave repetida en cualquier mapa, es un error.

## Campos de una entrada

Toda clave no listada aquí es un error («campo desconocido»).

### Obligatorios

| Campo | Valores | Notas |
|---|---|---|
| `id` | `^[a-zA-Z0-9_-]{1,64}$` | Es el nombre de función que ve la API del LLM. |
| `titulo` | texto | Nombre corto para personas. |
| `descripcion_llm` | texto | Lo que lee el LLM. Es costoso en tokens: ver «Presupuesto». |
| `justificacion` | texto | Por qué existe la entrada y qué se comprobó en real. Solo para personas (memoria del TFG). |
| `tipo` | `herramienta` · `comprobacion` · `accion` | `herramienta`: se expone al LLM tal cual. `comprobacion`: evalúa y devuelve un estado normalizado (H2/H3). `accion`: remediación con check/plan/apply/verify/rollback (H1+). |
| `nivel` | `lectura` · `accion` · `mutante` | Una `comprobacion` es siempre `lectura`; una `accion` es `accion` o `mutante`. |
| `riesgo` | `bajo` · `alto` | Criterio provisional: `mutante` → `alto`; el resto → `bajo`. |
| `sensibilidad` | `tecnica` · `personal` | `personal` si la salida puede contener nombres de usuario, de red, de volumen o rutas del usuario. |
| `perfiles` | lista no vacía ⊆ {`hogar`, `sistemas`} | Sin repetidos. |
| `plataforma` | mapa | Ver abajo. |
| `requisitos` | mapa | Ver abajo. |
| `motor` | `powershell` · `registro` · `comando` · `python` | Determina qué campo de contenido es obligatorio. |
| `area` | `cuentas` · `red` · `defender` · `dispositivo` · `sistema` · `actualizaciones` · `malware` | Agrupa las comprobaciones futuras que se expondrán al LLM por área, no una a una. |

### Opcionales

| Campo | Valores | Notas |
|---|---|---|
| `plantilla` | texto | **Obligatorio con `motor: powershell`**, prohibido con otros. |
| `argv` | lista de textos | **Obligatorio con `motor: comando`**, prohibido con otros. Se ejecuta con `shell=False`. |
| `clave_registro` | `{hive, ruta, valor}` | **Obligatorio con `motor: registro`**, prohibido con otros. `hive` ∈ `HKLM`·`HKCU`·`HKCR`·`HKU`·`HKCC`. Solo lectura (`nivel: lectura`). |
| `parametros` | `{nombre: [valores]}` | Solo con `powershell` o `comando`. Ver «Parámetros». |
| `severidad` | `alta` · `media` · `baja` | Obligatoria en `comprobacion`. |
| `peso` | entero 0–1000 | Obligatorio en `comprobacion`. |
| `marcos` | mapa | Ver «Marcos». |
| `timeout_s` | entero 1–86400 | Por defecto 30. |

`motor: python` no lleva `plantilla`, `argv`, `clave_registro` ni `parametros`: la lógica vive en una función registrada con el id de la entrada (reservado; sin uso en H1).

### `plataforma`

| Campo | Valores |
|---|---|
| `so` (obligatorio) | `windows` · `linux`. `powershell` y `registro` exigen `windows`. |
| `familias` | solo `linux`: lista ⊆ {`debian`, `rhel`, `arch`, `suse`}, o `null` (todas). |
| `build_min`, `build_max` | solo `windows`: enteros (build de Windows) o `null`; `build_min` ≤ `build_max`. |
| `ediciones` | solo `windows`: lista de textos o `null` (todas). Se comparan, sin distinguir mayúsculas, con el `EditionID` del registro (`Core` = Home, `Professional`, `Enterprise`, `Education`…). |

### `requisitos`

| Campo | Valores |
|---|---|
| `privilegios` (obligatorio) | `usuario` · `admin` (solo Windows) · `root` (solo Linux). `admin` y `root` equivalen a `requiere_admin` en el executor. |
| `binarios` | lista de nombres de binario (sin rutas), por defecto vacía. |

## Aplicabilidad al equipo

`catalogo.aplicable(entrada, capacidades, perfil)` devuelve `(bool, motivo)` y decide si una entrada se ofrece en este equipo. Las `capacidades` las detecta `src/plataforma/` (solo lectura, sin `subprocess`; se ven con `python -m src.plataforma`). Se comprueba, por este orden:

1. **Sistema:** `plataforma.so` debe coincidir con el del equipo (`windows`, `linux` u `otro`).
2. **Windows:** `build_min` ≤ build ≤ `build_max` (ambos inclusivos; si no se pudo leer el build, una entrada con límites no aplica) y `ediciones`.
3. **Linux:** `familias` debe contener la familia detectada (`debian`, `rhel`, `arch`, `suse`; por `ID` o `ID_LIKE` de `/etc/os-release`). Con `familias: null` aplica a todas, también a una distribución no reconocida.
4. **Binarios:** todos los de `requisitos.binarios` deben resolverse con `shutil.which` (en Linux, sobre un PATH fijo). Uno ausente excluye la entrada.
5. **Perfil:** el perfil activo (`hogar` por defecto) debe estar en `perfiles`.

Los **privilegios no excluyen** una entrada: una que exija `admin` o `root` sigue siendo aplicable aunque el proceso no esté elevado, y más adelante se marcará como `requiere_privilegios` (regla 14). `src/tools_schema.py` usa `aplicable` para enviar al LLM solo las herramientas del equipo: en Windows 10/11 las 25 actuales, en Linux ninguna.

## Plantillas, argv y marcadores

- Los comandos se construyen **solo** con la plantilla/argv del catálogo y los valores de `parametros` (reglas 2 y 13). Nada del LLM ni del usuario se concatena.
- **Con `parametros`**, la plantilla pasa por `str.format`: cada `{nombre}` debe estar declarado, no admite formato ni conversión (`{x:..}`, `{x!r}`, `{x.y}`) y las llaves literales se escriben `{{` y `}}`. Todo parámetro declarado debe usarse.
- **Sin `parametros`**, la plantilla se usa tal cual y las llaves de PowerShell son literales; solo se rechaza lo que parece un marcador suelto (`{nombre}`).

## Parámetros

`parametros` mapea cada nombre (`^[a-z_][a-z0-9_]{0,63}$`) a una lista cerrada de valores. Cada valor debe cumplir `^[A-Za-z0-9_.][A-Za-z0-9_.-]{0,63}$` (sin espacios, comillas, `;`, `$` ni guion inicial), no repetirse y ser un **texto**: en YAML hay que comillar `"True"` y `"False"`, porque sin comillas son booleanos y el cargador los rechaza.

## Lista de denegación

`LISTA_DENEGACION` (constante revisable en `src/catalogo.py`) prohíbe en plantillas, argv y valores de parámetros — también tras expandir todas las combinaciones de valores — estos tokens: `-DownloadFile`, `-DisableRealtimeMonitoring $true`, `-DisableIOAVProtection $true`, `Set-MpPreference -Exclusion*`, `Add-MpPreference -Exclusion*`, `HailMary`, `Invoke-Expression`, `IEX`, `DownloadString`, `Start-Process`, `cmd /c`, `bash -c`, `sh -c`, `sudo`, `su`, `pkexec`, `doas`, `rm -rf`, `Remove-Item -Recurse`, `Format-Volume`, `Clear-Disk`, `bcdedit`, `vssadmin delete`, `wevtutil cl`.

La comparación ignora mayúsculas y la cantidad de espacios, y respeta límites de palabra (`su` no casa con `Suma`). El `*` final significa «cualquier continuación».

## Marcos (CIS, CCN, ATT&CK, D3FEND, ENS)

La fuente prevista es `mapeo_marcos.csv`, con la cabecera exacta:

```
id,cis_benchmark,cis_id,cis_titulo_breve,cis_controls,ccn,attack,d3fend,ens,verificado_por,fecha
```

- `id` debe existir en el catálogo y no repetirse. Las listas (`cis_controls`, `ccn`, `attack`, `d3fend`, `ens`) se separan con `;`. `fecha` es `AAAA-MM-DD`.
- **Regla 15:** un mapeo solo es `verificado: true` si la columna `verificado_por` no está vacía. Sin ella el cargador lo deja en `verificado: false`. Los identificadores no se inventan: los aporta Juan.
- En el YAML, `marcos` admite `cis` (`{benchmark, id, titulo_breve}`), `cis_controls`, `ccn`, `attack`, `d3fend`, `ens` y `verificado`, pero `verificado: true` se rechaza (la verificación debe constar en el CSV). Un mismo id no puede tener `marcos` en el YAML y en el CSV a la vez.
- Las propuestas de la IA no van en el CSV: se anotan en `_propuestas_mapeo_IA.md` con la etiqueta «PROPUESTA IA — SIN VERIFICAR».

## Presupuesto de tokens

El esquema de herramientas que recibe el LLM no puede superar **3.000 tokens** (≈ caracteres/4, medido sobre el JSON compacto): el plan gratuito de Groq limita a 8.000 tokens por minuto. `tests/test_catalogo.py` lo comprueba. Por eso las futuras comprobaciones no se expondrán una a una, sino agrupadas por `area`.
