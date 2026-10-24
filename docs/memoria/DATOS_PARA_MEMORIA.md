# Datos para la memoria (P10, 2026-10-25)

Cifras extraídas del repositorio en el estado de la entrega intermedia (rama `master`, tras las correcciones de las pruebas en la VM, último commit de código `cf19e7d`). Las cifras de este documento se regeneraron el 25/10/2026 con la batería de 458 tests; la composición por fichero y tipo y la cobertura son las de esa ejecución. Nada está estimado: cada cifra sale de un comando o de un fichero que se cita. Donde una cifra es una aproximación (los tokens) o una clasificación hecha por reglas (los tipos de test) se dice expresamente.

## 0. Cómo se obtuvieron

| Dato | Fuente |
|---|---|
| Tests, por fichero | `python -m pytest --collect-only -q` (cuenta cada caso parametrizado como un test) |
| Resultado y cobertura | `python -m pytest --cov=src --cov-report=term-missing --junitxml=docs/memoria/evidencias/P10_junit.xml` → `evidencias/P10_pytest_final.txt` |
| Catálogo | `src.catalogo.cargar_catalogo()` recorriendo las 25 entradas (no transcrito a mano) |
| Esquema del LLM | `src.tools_schema.generar_tools_schema()` con un Windows 11 simulado, serializado en JSON compacto |
| Fases y niveles de automatización | `docs/memoria/REGISTRO_IA.md` |
| Incidencias | `docs/memoria/INCIDENCIAS_IA.md` |
| Mapeos a marcos | `catalogo/mapeo_marcos.csv` y campo `marcos` del catálogo |
| Commits y tamaños | `git log` y `git show --shortstat` |

Entorno de la batería: Windows 11, Python 3.14.7, pytest 9.1.1, pytest-cov 7.1.0. La misma batería, ejecutada en la VM (Windows 11 Home, compilación 26300, Python 3.13.14), también da 458 correctos (`evidencias/vm/vm_01_pytest.txt`).

## 1. Tests

Resultado final: **458 pasan, 0 fallan, 0 errores, 0 omitidos** en 12,9 s (`evidencias/P10_pytest_final.txt`). Un clon limpio del repositorio, con un entorno virtual nuevo e `pip install -r requirements-dev.txt`, pasó los 454 de la primera batería; la instalación desde cero en la VM pasó después los 458.

### 1.1 Evolución

| Momento | Tests | Variación | Evidencia |
|---|---|---|---|
| Inicio (línea base P7) | **185** | — | `evidencias/P07_pytest_baseline.txt` |
| Tras P7 (test de secretos) | 195 | +10 | `evidencias/P07_pytest_final.txt` |
| Tras P8 (catálogo) | 355 | +160 | `evidencias/P08_pytest.txt` |
| Tras P9 (plataforma) | 454 | +99 | `evidencias/P09_pytest.txt` |
| Tras P10 (batería con cobertura) | 454 | 0 | primera versión de `evidencias/P10_pytest_final.txt` |
| **Ahora (tras las pruebas en la VM)** | **458** | +4 | `evidencias/P10_pytest_final.txt` (regenerado), `evidencias/vm/vm_01_pytest.txt` |

Entre el inicio y ahora hay **273 tests más** (+148 %). Los 4 últimos son de las correcciones de la VM (2 en `test_agent.py`, INC-08, y 2 en `test_executor.py`, INC-10). Ningún assert de la batería inicial se modificó (PRUEBAS.md, P8 y P9); en INC-09 se reescribió un test de P9 (el de «no revela usuario ni equipo») para que no dependa del nombre de la máquina.

### 1.2 Por fichero

| Fichero | Inicio (185) | Ahora (458) | Introducido en |
|---|---:|---:|---|
| `tests/test_agent.py` | 16 | 18 | P3 (+2 en P10) |
| `tests/test_auditoria.py` | 26 | 26 | Post-P6 |
| `tests/test_cliente_observado.py` | 8 | 8 | Post-P6 |
| `tests/test_executor.py` | 99 | 101 | P2 (ampliado en Post-P6 y +2 en P10) |
| `tests/test_injection.py` | 3 | 3 | P6 |
| `tests/test_textos.py` | 24 | 24 | Post-P6 |
| `tests/test_tools_schema.py` | 9 | 9 | P3 |
| `tests/test_repo_sin_secretos.py` | — | 10 | P7 |
| `tests/test_catalogo.py` | — | 150 | P8 |
| `tests/test_catalogo_regresion.py` | — | 10 | P8 |
| `tests/test_plataforma.py` | — | 60 | P9 |
| `tests/test_catalogo_aplicable.py` | — | 25 | P9 |
| `tests/test_tools_schema_plataforma.py` | — | 14 | P9 |
| **Total** | **185** | **458** | |

### 1.3 Por tipo

Los tests no llevan etiqueta de tipo en el código. La clasificación se ha hecho **por reglas mecánicas aplicadas al fichero y al nombre del test** (primera regla que coincide): (1) `test_injection.py` → inyección; (2) `test_catalogo_regresion.py` o nombre con «equivale» → regresión; (3) nombre que indica un rechazo, un fallo gestionado o una exclusión («rechaza», «bloquea», «deniega», «ausente», «malformado», «ilegible», «fuera_de», «no_aplica», «maneja», etc.) → negativo; (4) `test_agent.py`, `test_audit_*` o nombres que mencionan el agente, `python -m src.plataforma` o un YAML temporal → integración simulada; (5) el resto → unitario. Es una aproximación reproducible, no una revisión test a test; la clasificación a mano por grupos está en `PRUEBAS.md`. No hay tests de tipo «VM»: las pruebas en VM son manuales; su registro está en `evidencias/vm/` y `evidencias/capturas/`.

| Tipo | Inicio (185) | Ahora (458) |
|---|---:|---:|
| Unitario | 88 | 175 |
| Negativo | 74 | 244 |
| Integración simulada | 20 | 26 |
| Regresión | 0 | 10 |
| Inyección | 3 | 3 |
| VM (automáticos) | 0 | 0 |
| **Total** | **185** | **458** |

Por fichero y tipo (ahora):

| Fichero | Unit. | Neg. | Integ. sim. | Regr. | Inyecc. |
|---|---:|---:|---:|---:|---:|
| `test_agent.py` | 0 | 7 | 11 | 0 | 0 |
| `test_auditoria.py` | 16 | 10 | 0 | 0 | 0 |
| `test_catalogo.py` | 14 | 136 | 0 | 0 | 0 |
| `test_catalogo_aplicable.py` | 11 | 13 | 1 | 0 | 0 |
| `test_catalogo_regresion.py` | 0 | 0 | 0 | 10 | 0 |
| `test_cliente_observado.py` | 4 | 4 | 0 | 0 | 0 |
| `test_executor.py` | 43 | 48 | 10 | 0 | 0 |
| `test_injection.py` | 0 | 0 | 0 | 0 | 3 |
| `test_plataforma.py` | 46 | 13 | 1 | 0 | 0 |
| `test_repo_sin_secretos.py` | 6 | 4 | 0 | 0 | 0 |
| `test_textos.py` | 19 | 4 | 1 | 0 | 0 |
| `test_tools_schema.py` | 8 | 1 | 0 | 0 | 0 |
| `test_tools_schema_plataforma.py` | 8 | 4 | 2 | 0 | 0 |

Observación para la memoria: los tests de inyección siguen siendo 3 desde P6; no se han ampliado en P7–P9 (ver incoherencia I-7).

### 1.4 Tamaño del código (líneas, `wc -l`)

| Carpeta | Ficheros `.py` | Líneas |
|---|---:|---:|
| `src/` (incluye `src/plataforma/`) | 10 | 1.847 |
| `app/` | 6 | 2.852 |
| `tests/` | 15 | 3.977 |
| `scripts/` | 4 | 259 |
| `catalogo/herramientas_llm.yaml` | — | 548 |

Repositorio: 13 commits en `master` entre 2026-08-27 y 2026-10-24; 87 ficheros versionados.

## 2. Catálogo de herramientas

25 entradas, todas de `tipo: herramienta`, motor `powershell`, plataforma Windows, perfiles `hogar` y `sistemas`. Las carpetas `catalogo/windows/` y `catalogo/linux/` están vacías (comprobaciones de H2 y H3). El reparto de `area`, `sensibilidad` y `riesgo` es una propuesta de la IA que Juan debe revisar (REGISTRO_IA, P8).

### 2.1 Por nivel

| Nivel | Herramientas |
|---|---:|
| lectura | 17 |
| accion | 4 |
| mutante | 4 |

Otras dimensiones: requieren administrador 12 (13 no); riesgo alto 4 (los mutantes) y bajo 21; con parámetros (enums) 3 (`set_firewall_profile`, `set_block_all_incoming`, `start_custom_scan`).

### 2.2 Por sensibilidad

| Sensibilidad | Herramientas | Cuáles |
|---|---:|---|
| técnica | 20 | el resto |
| personal | 5 | `get_detected_threats`, `get_active_network_profile`, `get_account_info`, `get_defender_exclusions`, `get_storage_status` |

Cruce con el nivel: lectura/técnica 12, lectura/personal 5, acción/técnica 4, mutante/técnica 4 (ninguna acción ni mutante es de sensibilidad personal).

### 2.3 Por área

| Área | Total | lectura | acción | mutante | personal |
|---|---:|---:|---:|---:|---:|
| red | 6 | 3 | 0 | 3 | 1 |
| malware | 5 | 1 | 3 | 1 | 1 |
| defender | 4 | 4 | 0 | 0 | 1 |
| sistema | 4 | 4 | 0 | 0 | 1 |
| dispositivo | 4 | 4 | 0 | 0 | 0 |
| actualizaciones | 1 | 0 | 1 | 0 | 0 |
| cuentas | 1 | 1 | 0 | 0 | 1 |
| **Total** | **25** | **17** | **4** | **4** | **5** |

## 3. Tamaño del esquema del LLM

`generar_tools_schema()` con un Windows 11 simulado devuelve las 25 herramientas.

| Medida | Valor |
|---|---:|
| Herramientas en el esquema | 25 |
| Caracteres (JSON compacto, UTF-8) | 7.278 |
| Bytes | 7.314 |
| **Tokens (aproximación caracteres ÷ 4)** | **≈ 1.819** (7.278 ÷ 4 = 1.819,5) |
| Límite fijado en el test (`LIMITE_TOKENS_ESQUEMA`) | 3.000 |
| Margen | ≈ 1.180 tokens (39 %) |
| Media por herramienta | ≈ 291 caracteres (≈ 73 tokens) |
| Mayor / menor | `set_block_all_incoming` 753 caracteres; `start_quick_scan` 182 |

**Aviso metodológico:** el proyecto no incluye tokenizador, así que «tokens» es la cota orientativa caracteres ÷ 4 que ya usan `PRUEBAS.md` y `_ESQUEMA.md`, no el recuento real de un modelo. Para citar un valor exacto en la memoria habría que medirlo con el tokenizador del modelo concreto (o con el campo `usage` de la respuesta de Groq). El esquema es el mismo en Windows 10 y 11 y vacío en Linux.

## 4. Cobertura (`src/`)

De `evidencias/P10_pytest_final.txt`:

| Módulo | Sentencias | No cubiertas | Cobertura | Líneas no cubiertas |
|---|---:|---:|---:|---|
| `src/catalogo.py` | 440 | 14 | **97 %** | 252-253, 306, 337, 340, 346, 405-406, 429, 493, 524-525, 569, 577 |
| `src/tools_schema.py` | 15 | 0 | **100 %** | — |
| `src/executor.py` | 111 | 5 | **95 %** | 67-70, 149 |
| `src/plataforma/` (3 ficheros) | 198 | 5 | **97,5 %** | todas en `deteccion.py`: 274-277, 285 |
| `src/plataforma/deteccion.py` | 189 | 5 | 97 % | 274-277, 285 |
| `src/plataforma/__init__.py` | 2 | 0 | 100 % | — |
| `src/plataforma/__main__.py` | 7 | 0 | 100 % | — |
| `src/agent.py` | 112 | 9 | 92 % | 84-85, 103-104, 126-127, 159-161 |
| `src/audit.py` | 10 | 0 | 100 % | — |
| `src/config.py` | 23 | 7 | 70 % | 40-60 (`cargar_perfil()` sin tests) |
| **Total `src/`** | **909** | **40** | **95,6 % (96 %)** | |

La cobertura se mide solo sobre `src/`; `app/` (2.852 líneas, incluida la vista de Streamlit) no está en el informe. Es cobertura de líneas, no de ramas. No se midió en ninguna fase anterior a P10.

## 5. Incidencias de la IA

`INCIDENCIAS_IA.md` contiene **12 incidencias** (INC-01 a INC-12): las siete primeras de la revisión de P10 y las cinco últimas de las pruebas en la VM. Las causas raíz son hipótesis de la IA que Juan debe confirmar.

| Desglose | Resultado |
|---|---|
| Por forma de detección | Revisión de coherencia documental: 3 (INC-01, INC-02, INC-03) · contraste con la memoria preliminar: 1 (INC-04) · test automático: 1 (INC-05) · contraste del autor con fuentes oficiales (attack.mitre.org y anexo II del RD 311/2022): 2 (INC-06, INC-07) · pruebas en la VM: 5 (INC-08 por el error 413 de Groq, INC-09 por un test que falló en la VM, INC-10 por revisión del extracto de auditoría, INC-11 e INC-12 por revisión de las capturas) · revisión del diff: 0 |
| Por módulo | Memoria (`ESTADO_FUNCIONALIDADES.md`): 2 (INC-01, INC-03) · memoria (`CAMBIOS.md`): 1 (INC-04) · catálogo, documentación (`_ESQUEMA.md`): 1 (INC-02) · evidencias de P10: 1 (INC-05) · propuestas de mapeo (`_mapeo_marcos_razonamiento.md`): 2 (INC-06, INC-07) · código de `src/`: 2 (INC-08 en `src/agent.py`, INC-10 en `src/executor.py`) · tests: 1 (INC-09) · comportamiento del modelo, sin corrección: 2 (INC-11, INC-12) |
| Por fase de origen | P2: 1 (INC-10) · P3: 1 (INC-08) · P7: 2 · P8: 2 · P9: 1 (INC-09) · P10: 5 (INC-05, INC-06, INC-07, INC-11, INC-12) |

Las siete primeras no afectan al código de `src/`. INC-08 e INC-10 son fallos de código de `src/`, corregidos con test de regresión; INC-09 es un test frágil, corregido; INC-11 e INC-12 son errores del modelo en tiempo de ejecución que **no se han corregido** (limitaciones conocidas). Si Juan recuerda algún comportamiento incorrecto de la IA en el código que corrigiera antes, debe añadirse con su causa raíz y su test de regresión.

## 6. Fases y nivel de automatización

Niveles de `REGISTRO_IA.md`: N2 generación supervisada de fragmentos, N3 módulo completo con revisión del diff, N4 desarrollo agéntico completo. Los niveles son una **propuesta** razonada (la escribió la IA a partir del tamaño de cada commit) que Juan debe validar. El tamaño es el de `git show --shortstat`.

| Fase | Fecha | Commit | Tamaño | Nivel |
|---|---|---|---|---|
| P0 Estructura inicial | 2026-08-27 | `2728b9a` | 16 ficheros, +162 | N2 |
| P1 Doble hello world | 2026-08-27 | `7922ebd` | 2 ficheros, +145 | N2 |
| P2 Capa ejecutora | 2026-08-28 | `6c3d8c2` | 5 ficheros, +689 | N3 |
| P3 Agente y CLI | 2026-08-28 | `76ffdcd` | 6 ficheros, +631 | N3 |
| P4 Streamlit | 2026-08-28 | `b87ba23` | 4 ficheros, +339 −9 | N3 |
| P5 Modo privado (Ollama) | 2026-08-28 | `b22a112` | 8 ficheros, +143 −16 | N2 |
| P6 Demo e inyección | 2026-08-28 | `6d228a1` | 2 ficheros, +354 | N2 |
| Post-P6: WHITELIST a 25 | 2026-09-01 | `1aee76d` | 5 ficheros, +1.530 −6 | N3 |
| Post-P6: paquete de diseño | 2026-09-01 | `3d9b3cb` | 9 ficheros, +4.114 | N/A (material de diseño) |
| Post-P6: módulos de apoyo UI | 2026-09-01 | `4ae26e3` | 8 ficheros, +2.111 | N3 |
| Post-P6: vista Streamlit | 2026-09-01 | `26cbe3b` | 4 ficheros, +2.877 −156 | N3 |
| P7 Línea base | 2026-10-22 | `4b5c408` (junto con P8) | — | N4 |
| P8 Catálogo YAML | 2026-10-23 | `4b5c408` | 31 ficheros, +3.175 −380 (P7 + P8) | N4 |
| P9 Plataforma | 2026-10-24 | `2f1723c` | 27 ficheros, +1.534 −12 | N4 |
| P10 Entrega intermedia | 2026-10-24 y 25 | `f22343c`, `0bf0154`, `68e4bf1`, `b350979`, `50b698b`, `cf19e7d` | sin funcionalidad nueva (3 correcciones de las pruebas en la VM) | N4 (propuesto) |

Recuento: 14 filas con nivel (sin contar P10): N2 = 4 (P0, P1, P5, P6), N3 = 6, N4 = 3 (P7, P8, P9), N/A = 1; con P10, N4 = 4. No hay filas N0 ni N1 en el registro. Todo el código generado figura como aceptado sin cambios.

## 7. Funcionalidades (F01–F27)

De `ESTADO_FUNCIONALIDADES.md`: **3 completadas** (F01, F03, F04), **4 en curso** (F02, F08, F12, F27) y **20 pendientes**. Origen declarado: «IA supervisada» en las 7 que existen (F01, F02, F03, F04, F08, F12, F27); ninguna «alumno», «mixto» ni «software existente».

## 8. Mapeos a marcos

| Concepto | Cifra |
|---|---:|
| Herramientas con mapeo **verificado** (`verificado: true`, con `verificado_por`) | **14 de 25** (CIS Controls v8.1, ATT&CK y ENS; verificados por Juan Sotos el 2026-10-24) |
| Propuestas de mapeo de la IA pendientes de verificar | **0** (las 14 se verificaron y corrigieron; las 11 restantes no tienen propuesta; razonamiento y perfil en `catalogo/_mapeo_marcos_razonamiento.md`) |
| Filas en `catalogo/mapeo_marcos.csv` | 14 |
| Entradas del catálogo con el campo `marcos` en el YAML | 0 |
| Entradas del catálogo sin mapeo (`verificado: false` por defecto) | 11 de 25 |

Los 25 identificadores heredados son herramientas del LLM, no comprobaciones; los mapeos CIS/CCN/ATT&CK corresponden sobre todo a las comprobaciones de H2 y H3, que aún no existen. Según la regla 15 el CSV lo rellena Juan. Durante la verificación la IA cometió dos errores (identificadores de ATT&CK obsoletos y una medida del ENS mal asignada), registrados como INC-06 e INC-07; CIS Controls v8.1 se contrastó sin errores. CIS Benchmark, CCN-STIC y D3FEND siguen sin mapeo. Los mapeos son orientativos, no una declaración de conformidad.

## 9. Seguridad (comprobaciones de P10)

| Comprobación | Resultado |
|---|---|
| `tests/test_repo_sin_secretos.py` | 10 de 10 en verde |
| `git log --all -G "gsk_[A-Za-z0-9]{10,}" --oneline` | sin coincidencias |
| Ficheros versionados en `logs/`, `data/`, `.env`, `*.jsonl` o `.coverage` | ninguno, ni en el índice ni en el historial |
| `logs/audit.jsonl` y `.env` | ignorados por `.gitignore` (`git check-ignore`) |
| Nombre de usuario de Windows, nombre del equipo, correo, rutas `C:\Users\…` e IPs en ficheros versionados | ninguno |
| Evidencias nuevas | `P10_junit.xml` incluía el nombre del equipo en `hostname=` y `P10_pytest_final.txt` rutas absolutas del repositorio: se sustituyeron por `anonimizado` y rutas relativas / `<repo>`. Los identificadores de los 4 casos de `test_los_patrones_detectan_claves_falsas` en el XML contenían las claves sintéticas del test y hacían fallar el propio test de secretos; se renombraron a `caso_sintetico_1…4` (el test no se modificó). Se repitió el mismo saneado al regenerar ambos ficheros con los 458 tests |
| Evidencias de la VM (`evidencias/vm/`, `evidencias/capturas/`) | El log de auditoría de la VM contiene el usuario y el nombre del equipo reales (`get_account_info`), por lo que no se versiona: se extrajo un resumen sin resultados y solo las líneas de la mutación. La salida de pytest se anonimizó (`rootdir`). Las capturas de PowerShell muestran la ruta de la cuenta local de la VM (`C:\Users\juan\…`), que coincide con el nombre de pila del autor; no aparece ninguna clave ni el nombre del equipo. El test de secretos (10 de 10) sigue en verde con las evidencias dentro |

Observaciones (no son fallos): los metadatos de los commits llevan el nombre y el correo del autor, como es habitual en git; y la historia anterior a la reescritura (`refs/original`) se eliminó tras la revisión (ver I-9).

## 10. Incoherencias detectadas en la revisión

Revisión de `ESTADO_FUNCIONALIDADES.md` (F01–F27), `CAMBIOS.md`, `REGISTRO_IA.md`, `PRUEBAS.md`, `catalogo/_ESQUEMA.md` y `CLAUDE.md` entre sí y con el código. Estado: **corregida** = ya cambiada en P10; **abierta** = decisión de Juan.

| ID | Incoherencia | Estado |
|---|---|---|
| I-1 | `REGISTRO_IA.md` daba «pendiente (lo hará Juan)» como commit de P7, P8 y P9, pero ya existen: P7 y P8 van juntos en `4b5c408` («Migra la WHITELIST… y cierra la línea base P7») y P9 en `2f1723c`. | Corregida (columna Commit). La columna «Aceptado sin cambios» de P7–P10 pasó a «Revisado y aceptado por el autor» tras su revisión del diff. |
| I-2 | `ESTADO_FUNCIONALIDADES.md` F08 citaba `tests/test_auditoria.py` (26 tests) como prueba de `src/audit.py`, pero ese fichero prueba el lector de la interfaz `app/auditoria.py`. `src/audit.py` se prueba desde `tests/test_executor.py` (los `test_audit_*`) y `tests/test_agent.py`; su cobertura es del 100 %. | Corregida (F08). |
| I-3 | `ESTADO_FUNCIONALIDADES.md` decía «actualizado en P9»; P10 revisó el documento. `PRUEBAS.md` (P8 y P9) decía que la cobertura «no está medida». | Corregidas (cabecera de ESTADO; sección P10 de PRUEBAS con la cobertura). |
| I-4 | `catalogo/_ESQUEMA.md` decía que `tests/test_catalogo.py` comprueba el presupuesto de tokens; ese test está en `tests/test_catalogo_regresion.py` (`test_el_esquema_cabe_en_el_presupuesto_de_tokens`). | Corregida. |
| I-5 | `CLAUDE.md` indicaba para Groq el modelo `llama-3.3-70b-versatile`, que ya no se usa (`src/config.py` usa `openai/gpt-oss-20b`; `CAMBIOS.md` lo registra). | Corregida: `CLAUDE.md` indica `openai/gpt-oss-20b`. |
| I-6 | `CLAUDE.md` describía el estado hasta P6, daba la WHITELIST como única fuente de verdad y omitía `pyyaml` y `pytest-cov`. | Corregida: fuente de verdad = catálogo, dependencias actualizadas, comandos nuevos y estado por fases con P7–P10. |
| I-7 | `ESTADO_FUNCIONALIDADES.md` F27 decía que los tests de inyección «se amplían en cada fase», pero siguen siendo 3 desde P6. | Corregida: el texto dice que pueden ampliarse según lo realizado en cada fase y que, si es necesario, se generarán nuevos. |
| I-8 | `REGISTRO_IA.md` indicaba Sonnet 5.5 en todas las fases (P0–P6 eran en realidad Sonnet 5, confirmado por el autor), pero los commits `1aee76d`, `4ae26e3` y `26cbe3b` (y el de diseño `3d9b3cb`) llevaban `Co-Authored-By: Claude Opus 5` antes de reescribir el historial. | Corregida: esas tres filas figuran como Opus 5 y el criterio lo explica. El historial de `master` ya no contiene ningún co-autor (0 coincidencias) y su único autor es `JuanSotos`. |
| I-9 | `git log --all` mostraba dos líneas de historia (la actual y la anterior a la reescritura, en `refs/original`). | Corregida: se eliminó `refs/original`, se caducó el reflog y se ejecutó `git gc --prune=now`; solo queda la línea actual (13 commits) y `origin/master`. Los hashes de la documentación son los de esa línea. |
| I-10 | `REGISTRO_IA.md` fecha P8 el 2026-10-23 y P7 el 2026-10-22, pero su commit es del 2026-10-24: las fechas del registro son las de trabajo y las del commit son las de confirmación. | Informativa: aclarar en la memoria cuál se usa. |
| I-11 | No constaba la Tabla 5 de la memoria preliminar para saber si la WHITELIST de 25 herramientas, el rediseño de la interfaz y las reglas v2 eran desviaciones. | Resuelta con «Planteamiento final y estructura»: ninguna de las tres es desviación de calendario ni de alcance (H0 ya preveía 25 herramientas, interfaz y 185 tests; la Tabla 3 cita el diseño de la interfaz). Las reglas v2 sí son una diferencia de estrategia (la memoria dice «ocho reglas») y se añadió su fila a `CAMBIOS.md`. Detalle en `PLANIFICACION_RESTANTE.md`, apartado 4. |
| I-12 | La evidencia de las pruebas manuales en VM estaba vacía mientras `PRUEBAS.md` y `ESTADO_FUNCIONALIDADES.md` dependían de ella para F04, F12 y P2–P6. | Cerrada en parte: las pruebas se hicieron el 24 y 25/10/2026 y constan en `evidencias/vm/` y `evidencias/capturas/` (F04 en Windows 11; F12 con lectura, EICAR y acción con confirmación). Siguen sin evidencia propia las pruebas de P2–P6, Linux, Windows 10 y el modo privado. |
| I-13 | F02 (proveedor dual) figura «en curso» y la cobertura lo confirma: `src/config.py` está al 70 % porque `cargar_perfil()` (líneas 40-60) no tiene tests. | Consistente; sigue pendiente de test. |
| I-14 | Las filas 1, 2 y 4 de `CAMBIOS.md` figuraban como cambios «respecto a la entrega preliminar», pero la memoria ya describe el modelo `openai/gpt-oss-20b`, el catálogo YAML y el esquema filtrado por equipo: comparaban con el `CLAUDE.md` y el prototipo originales. | Corregida (opción A): `CAMBIOS.md` tiene ahora la tabla 1, con lo que se aparta de la memoria preliminar (agrupación por área y reglas 8→18), y la tabla 2, «Decisiones de diseño durante el desarrollo», con las otras tres y su base de comparación. Se reescribió el motivo de la fila del catálogo, que contradecía la memoria. |
| I-15 | Cifras de la memoria preliminar desfasadas («185 actualmente», «ocho reglas», Tabla 3 sin versión de modelo). | Descartada: la memoria adjuntada es una versión antigua (entrega de planteamiento y estructura) y no se modifica; la memoria de la entrega intermedia recogerá las cifras actuales (458 tests, 18 reglas). |

Comprobado sin incoherencias: los 27 identificadores F01–F27 están todos; los recuentos de tests citados en ESTADO, PRUEBAS y REGISTRO (16, 26, 150, 10, 25, 14, 60, 99, 3, 24, 9, 8) coinciden con `pytest --collect-only`; los tamaños de commit de REGISTRO_IA coinciden con `git show --shortstat`; las 4 filas de `CAMBIOS.md` coinciden con el código (modelo de Groq en `src/config.py`, WHITELIST derivada del catálogo en `src/executor.py`, esquema de 25 herramientas ≈ 1.819 tokens, fixture autouse en `tests/conftest.py`).
