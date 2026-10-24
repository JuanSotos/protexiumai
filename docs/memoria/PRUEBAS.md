# Pruebas

Tipos de test: unitario / negativo / inyección / integración simulada / VM.
Todos los tests automáticos usan subprocess y LLM mockeados y no ejecutan acciones reales sobre el sistema. Las pruebas con efectos sobre el sistema se hacen solo en la VM (regla 17).

Las secciones P0–P6 y Post-P6 se han reconstruido de `git log`/`git show` y de los propios ficheros de test. El recuento por fichero es el **actual** (línea base P7), no el de cada fase. La cobertura de código **no se midió** en ninguna fase anterior a P7 (`pytest-cov` no estaba instalado), así que no se inventan porcentajes.

**Pruebas manuales en VM.** El repositorio documenta el procedimiento (snapshots «Base limpia» y «Demo lista» de VirtualBox en `docs/demo_escenarios.md` y `README.md`, y el script `scripts/verificar_whitelist.py`), pero **no contiene un registro de resultados obtenidos ni capturas**. Por eso en cada fase se indica el procedimiento disponible y el campo «resultado obtenido» queda como pendiente de aportar con la captura correspondiente, en `evidencias/vm/` y `evidencias/capturas/`.

## P0 — Estructura inicial (`2728b9a`)
- Tests añadidos: ninguno (solo el paquete `tests/__init__.py`).
- Pruebas manuales en VM: no aplica.

## P1 — Doble hello world (`7922ebd`)
- Tests añadidos: ninguno. Verificación manual con `scripts/hello_llm.py` (conexión con el LLM) y `scripts/hello_ps.py` (ejecución de PowerShell desde Python); ambos se ejecutan a mano y dependen de la API key y del sistema.
- Pruebas manuales en VM: no aplica (solo lectura y llamada al LLM).

## P2 — Capa ejecutora (`6c3d8c2`)
- Fichero de test: `tests/test_executor.py` (hoy 99 tests) con `tests/conftest.py`, que aísla el executor y la auditoría del sistema real.

| Grupo de tests | Qué verifica | Tipo |
|---|---|---|
| `test_whitelist_contiene_exactamente_las_25_herramientas` | La WHITELIST contiene exactamente las herramientas esperadas. | unitario |
| `test_execute_rechaza_*` (tool_id desconocido, parámetro no declarado, parámetro faltante, valor fuera de enum) | La validación cierra el paso a cualquier cosa fuera de la WHITELIST y de los enums. | negativo |
| `test_comando_*_es_exacto` | El comando generado es exactamente la plantilla fija con los valores validados. | unitario |
| `test_execute_bloquea_sin_admin...`, `test_lectura_no_comprueba_admin` | Sin administrador no se ejecutan las herramientas que lo requieren y nunca se intenta elevar. | negativo |
| `test_execute_maneja_timeout`, `..._powershell_no_encontrado`, `..._returncode_no_cero`, `..._json_invalido` | Los fallos de PowerShell se devuelven como error explicado, sin excepción. | negativo |
| `test_audit_*` | Toda llamada, aceptada o rechazada, queda registrada con el motivo. | integración simulada |
| `test_execute_aborta_mutante_si_falla_auditoria_previa` | Una mutación no se ejecuta si no se puede auditar antes. | negativo |

- Pruebas manuales en VM: procedimiento en `scripts/verificar_whitelist.py` (comprueba que no se puede ejecutar nada fuera de la WHITELIST). Resultado obtenido: pendiente de aportar con captura.

## P3 — Agente y CLI (`76ffdcd`)
- Ficheros de test: `tests/test_agent.py` (hoy 16 tests) y `tests/test_tools_schema.py` (hoy 9 tests). El cliente LLM va mockeado.

| Grupo de tests | Qué verifica | Tipo |
|---|---|---|
| `test_tool_lectura_se_ejecuta_sin_pedir_confirmacion` | Las lecturas no piden confirmación. | integración simulada |
| `test_tool_*_con_confirmacion_true/false...` | Las acciones y mutaciones solo se ejecutan con un «sí» explícito; con «no» no se ejecutan y se audita la cancelación. | integración simulada / negativo |
| `test_sin_callback_confirmar_deniega_por_defecto` | Sin callback de confirmación se deniega. | negativo |
| `test_argumentos_invalidos...`, `test_tool_id_alucinado...`, `test_limite_de_iteraciones...` | El agente sobrevive a argumentos inválidos, herramientas inventadas y bucles. | negativo |
| `test_schema_*`, `test_fuente_unica_de_verdad` | El esquema para el LLM se genera desde la WHITELIST y es serializable. | unitario |

- Pruebas manuales en VM: pendiente de aportar (conversación real por consola).

## P4 — Interfaz Streamlit (`b87ba23`)
- Tests añadidos: ninguno (la vista de Streamlit no tiene tests automáticos; los módulos de apoyo se testean desde `4ae26e3`).
- Pruebas manuales: confirmación por botones en la interfaz. Resultado obtenido: pendiente de aportar con captura.

## P5 — Modo privado con Ollama (`b22a112`)
- Tests añadidos: `test_audit_propaga_proveedor` y `test_audit_proveedor_por_defecto_es_none` en `tests/test_executor.py` (la auditoría registra el proveedor activo, o `None` si no se indica) — tipo unitario.
- Verificación end-to-end documentada en `README.md`: sesión de 10 turnos con `llama3.2:3b` y function calling; el modelo eligió la herramienta correcta y generó argumentos JSON válidos en 13 de 14 llamadas, y el único fallo (un parámetro no declarado) fue rechazado por el validador sin llegar a PowerShell. Se apoya en `scripts/check_local.py`. Captura: pendiente de aportar.

## P6 — Demo y tests de inyección (`6d228a1`)
- Fichero de test: `tests/test_injection.py` (3 tests, cliente mockeado).

| Test | Qué verifica | Tipo |
|---|---|---|
| `test_contenido_malicioso_en_resultado_de_tool_no_se_ejecuta_sin_confirmacion_explicita` | Un nombre de amenaza que ordena desactivar el firewall no provoca ninguna mutación sin confirmación. | inyección |
| `test_contenido_malicioso_sin_callback_de_confirmacion_se_deniega_por_defecto` | Sin callback de confirmación, la orden inyectada se deniega. | inyección |
| `test_tool_id_alucinado_es_rechazado_limpiamente_y_agente_no_se_rompe` | Una herramienta inventada se rechaza y el agente continúa. | inyección / negativo |

Estos tests no prueban si un LLM real «obedecería» el texto inyectado, sino que agente y executor nunca ejecutan una acción sin confirmación, pase lo que pase en la salida de la herramienta.
- Pruebas manuales en VM: guion en `docs/demo_escenarios.md` (restaurar el snapshot «Demo lista» antes de cada ensayo). Resultado obtenido de los ensayos: pendiente de aportar con captura.

## Post-P6 (`1aee76d`, `3d9b3cb`, `4ae26e3`, `26cbe3b`)
- `1aee76d` (WHITELIST de 7 a 25 herramientas): añade unos 67 tests en `tests/test_executor.py`, `tests/test_agent.py` y `tests/test_tools_schema.py`: comando exacto por herramienta (unitario), normalización de listas vacías o de un solo elemento (unitario), comprobación de administrador (negativo), auditoría de las nuevas acciones (integración simulada) y valores fuera de enum (negativo). Pruebas manuales en VM de las herramientas de lectura nuevas: documentadas en los comentarios de `src/executor.py` («Comprobado en real»); capturas pendientes.
- `3d9b3cb`: paquete de diseño; sin tests.
- `4ae26e3` (módulos de apoyo de la interfaz): añade `tests/test_auditoria.py` (26 tests, lector del registro de auditoría — unitario), `tests/test_cliente_observado.py` (8 — unitario) y `tests/test_textos.py` (24 — tablas de redacción en llano, unitario).
- `26cbe3b` (vista Streamlit rediseñada): sin tests automáticos; revisión visual manual, captura pendiente.

## P7 — Línea base de la entrega intermedia (2026-10-22)

Sin funcionalidad nueva: no se modifica ningún módulo de `src/` ni de `app/`.

### Tests añadidos — `tests/test_repo_sin_secretos.py`

| Test | Qué verifica | Tipo |
|---|---|---|
| `test_env_no_esta_versionado` | `.env` no figura en el índice de git (`git ls-files --cached`). | negativo |
| `test_ningun_fichero_contiene_claves` | Ningún fichero versionado ni pendiente de versionar contiene `gsk_…` / `sk-…` de 20+ caracteres ni asignaciones de `api_key`/`token`/`secret` con literal de 16+ caracteres. El mensaje de fallo da fichero:línea, nunca el valor. | negativo |
| `test_env_example_solo_tiene_valores_vacios_o_de_ejemplo` | En `.env.example` las claves sensibles van vacías o con un marcador de ejemplo evidente. | negativo |
| `test_los_patrones_detectan_claves_falsas` (4 casos) | Los patrones detectan claves sintéticas (no reales). | unitario |
| `test_los_patrones_no_marcan_valores_inocuos` (3 casos) | Valores cortos, vacíos o leídos del entorno no producen falsos positivos. | unitario |

### Resultado
- Línea base antes de los cambios: **185 passed** (`evidencias/P07_pytest_baseline.txt`).
- Tras P7: **195 passed** = 185 + 10 casos de `test_repo_sin_secretos.py` (`evidencias/P07_pytest_final.txt`). Sin fallos.
- Instantánea del esquema de herramientas: `tests/fixtures/schema_p7.json` (25 herramientas), referencia de regresión para P8.

### Cobertura de los módulos tocados
No aplica: P7 no modifica módulos de `src/` ni de `app/`. `pytest-cov` queda declarado en `requirements-dev.txt` pero no se ha instalado ni ejecutado en esta fase.

### Pruebas manuales en VM
Ninguna en P7 (sin cambios que afecten al sistema).

### Revisión del historial de git
`git log --all -G "gsk_[A-Za-z0-9]{10,}" --oneline` no devuelve coincidencias: no hay claves de Groq en el historial.

## P8 — Catálogo YAML (2026-10-23)

Migración de la WHITELIST en código al catálogo `catalogo/herramientas_llm.yaml` (F03). Sin herramientas ni comprobaciones nuevas.

### Tests añadidos

`tests/test_catalogo.py` (150 casos, cargador) y `tests/test_catalogo_regresion.py` (10 casos). No se modifica ningún assert de la batería anterior ni ningún fichero de test existente.

| Grupo | Qué verifica | Tipo |
|---|---|---|
| `test_catalogo_real_*`, `test_carga_valida_*`, `test_comprobacion_valida_*`, `test_entrada_linux_*` | El catálogo real carga las 25 herramientas; cargan entradas válidas de cada motor (powershell, comando, registro) y carpetas `windows/` y `linux/` vacías. | unitario |
| `test_rechaza_campo_desconocido*`, `test_rechaza_campo_obligatorio_ausente` (13 campos) | Campos desconocidos (también anidados y en la cabecera) y campos obligatorios ausentes. | negativo |
| `test_rechaza_ids_duplicados_*`, `test_rechaza_clave_duplicada_en_el_yaml` | Ids duplicados en un fichero y entre ficheros; claves YAML repetidas. | negativo |
| `test_rechaza_enum_invalido` (12 casos), `test_rechaza_id_con_formato_invalido` | Enums fuera de rango e ids que no cumplen `^[a-zA-Z0-9_-]{1,64}$`. | negativo |
| `test_rechaza_marcador_*`, `test_rechaza_parametro_declarado_pero_no_usado`, `test_rechaza_marcadores_con_formato_o_accesos`, `test_llaves_*` | Marcadores `{x}` no declarados, parámetros sin usar, formato o accesos en marcadores; las llaves de PowerShell siguen siendo literales. | negativo / unitario |
| `test_rechaza_booleanos_yaml_sin_comillar`, `test_rechaza_valores_de_enum_peligrosos` | `True`/`False` sin comillar y valores de enum con espacios, `;`, `$`, comillas o guion inicial. | negativo |
| `test_lista_de_denegacion_rechaza_cada_token_en_plantillas` / `..._en_argv` (24 + 24 casos) | Cada token de la lista de denegación se rechaza en plantillas y en argv; también tras expandir parámetros y en los valores de enum. | negativo / inyección |
| `test_denegacion_ignora_mayusculas_y_espacios`, `test_denegacion_respeta_limites_de_palabra` | Sin falsos positivos (`su` no casa con `Summary`) ni evasiones por mayúsculas o espacios. | unitario / negativo |
| `test_csv_*`, `test_mapeo_sin_verificado_por_*`, `test_yaml_no_puede_afirmar_verificado_true`, `test_el_csv_real_*` | Fusión del CSV de marcos; un mapeo sin `verificado_por` queda `verificado: false` (regla 15); ids inexistentes, duplicados, cabecera y fecha incorrectas. | unitario / negativo |
| `test_esquema_equivale_semanticamente_al_de_p7`, `test_el_orden_..._se_conserva` | El esquema generado equivale a `tests/fixtures/schema_p7.json` (nombres, parámetros, enums, obligatorios y redacción) e incluso conserva el orden. | regresión |
| `test_whitelist_derivada_*`, `test_el_comando_generado_...` | La WHITELIST derivada conserva plantilla, descripción, enums, nivel, administrador y timeout de las 25 herramientas (`tests/fixtures/whitelist_p7.json`, generado con el código anterior) y el comando ejecutado sigue siendo la plantilla con los valores validados. | regresión |
| `test_el_esquema_cabe_en_el_presupuesto_de_tokens` | El esquema no supera 3.000 tokens. | unitario |

Diferencias de redacción entre el esquema de P7 y el actual: **ninguna** (`DIFERENCIAS_DE_REDACCION` está vacío en el test).

Comprobación de que los tests negativos detectan fallos: se desactivó temporalmente, una a una, la lista de denegación, la comprobación de marcadores, la de campos desconocidos y la regla de `verificado`; en los cuatro casos algún test falló. El código se restauró después.

### Presupuesto de tokens
Medida: 7.278 caracteres del esquema (JSON compacto UTF-8) ÷ 4 = **≈ 1.819 tokens** frente a un límite de **3.000** (motivo: límite de 8.000 tokens/minuto del plan gratuito de Groq). Margen de ≈ 1.180 tokens. La aproximación caracteres/4 es una cota orientativa, no el recuento real del tokenizador.

### Resultado
- Línea base antes de los cambios: **195 passed**.
- Tras P8: **355 passed** = 195 + 150 + 10 (`evidencias/P08_pytest.txt`). Sin fallos.
- Prueba de humo del agente con el LLM simulado: una lectura (`get_time_service_status`) se ejecuta, se audita y el agente envía 25 herramientas al LLM, igual que antes.

### Cobertura de los módulos tocados
No medida: `pytest-cov` no está instalado en el entorno (ver P7).

### Pruebas manuales en VM
Ninguna en P8: la migración no cambia los comandos ni añade acciones. Antes de dar la fase por cerrada conviene repetir en la VM una lectura y una acción con confirmación para ver que el comando ejecutado es idéntico.

## P9 — Detección de plataforma y capacidades (2026-10-24)

Paquete `src/plataforma/` (F04), `catalogo.aplicable()` y esquema del LLM filtrado por equipo. Sin herramientas ni comprobaciones nuevas.

### Tests añadidos

`tests/test_plataforma.py` (60), `tests/test_catalogo_aplicable.py` (25) y `tests/test_tools_schema_plataforma.py` (14): **99 tests**. No se modifica ningún assert de la batería anterior. Único cambio en un fichero existente: `tests/conftest.py` gana una fixture autouse que simula un Windows 11 Pro (build 26100) parcheando los lectores de bajo nivel, para que la batería no dependa del equipo en el que se ejecute. Ningún test lee el registro, `/etc/os-release` ni `/sys` reales y ninguno lanza subprocesos.

| Grupo | Qué verifica | Tipo |
|---|---|---|
| `test_familia_y_campos_de_cada_distribucion` (8 casos) | Con las fixtures de `tests/fixtures/os-release/` (ubuntu-24.04, debian-12, kali-rolling, linuxmint-22, fedora-41, rocky-9, arch, opensuse-tumbleweed) la familia (debian / rhel / arch / suse), `ID`, `VERSION_ID` y `NAME` son los correctos; solo Kali es `es_kali`. | unitario |
| `test_os_release_malformado_o_vacio_...`, `test_sin_fichero_os_release_...` | Un os-release malformado, vacío o inexistente da familia «desconocida» sin excepción. | negativo |
| `test_la_familia_se_deduce_de_id_like_...`, `test_el_id_prevalece_...` | `ID_LIKE` sirve de respaldo, `ID` tiene prioridad y `opensuse*` es suse. | unitario |
| `test_parser_*` (4) | Parseo propio: comillas dobles (con escapes) y simples, comentarios, saltos CRLF, líneas mal formadas descartadas sin perder las buenas, bytes raros. | unitario / negativo |
| `test_windows_10_y_11_home_y_pro` (6 casos) | Builds 19045 (Windows 10) y 26100 (Windows 11), ediciones `Core` (Home) y `Professional`, y el límite 22000/21999 de `es_windows11`. | unitario |
| `test_el_registro_se_abre_solo_en_modo_lectura_...`, `test_sin_winreg_o_sin_clave_...` | Con un `winreg` falso: se abre `HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion` con `KEY_READ` (sin bit de escritura) y un registro ilegible devuelve vacío. | unitario / negativo |
| `test_registro_ilegible_...`, `test_valores_de_registro_corruptos_...` | Valores ausentes o corruptos dejan los campos en su valor neutro sin excepción. | negativo |
| `test_comprobacion_de_administrador_...`, `test_sin_windll_...`, `test_es_root_...` | `IsUserAnAdmin` y `os.geteuid()` simulados; sin ellos, no hay privilegios. | unitario |
| `test_deteccion_de_mac`, `test_mac_se_propaga_...` | AppArmor (`Y`/`N`), SELinux (`0` permisivo y `1`), prioridad de SELinux, contenido basura y ficheros ausentes. | unitario |
| `test_clasificacion_del_sistema`, `test_so_otro_...` | `win32`, `linux`, `darwin`, `freebsd` → windows / linux / otro. | unitario |
| `test_binarios_*`, `test_una_ruta_relativa_...`, `test_los_binarios_declarados_...` | Binarios resueltos a ruta absoluta o `None`, PATH fijo en Linux, ruta relativa rechazada y recogida de los binarios declarados en el catálogo. | unitario |
| `test_la_deteccion_no_importa_subprocess_...` | El módulo no importa `subprocess` ni usa `os.system`/`os.popen`. | unitario (estático) |
| `test_a_dict_...`, `test_python_m_src_plataforma_...` | El JSON del diagnóstico es válido, no contiene el usuario ni el nombre del equipo y abrevia rutas bajo el directorio personal. | unitario / integración simulada |
| `test_una_entrada_de_windows_...`, `test_entrada_solo_para_windows_11_no_aplica_en_windows_10`, `test_build_max_...`, `test_los_limites_de_build_...` | `aplicable()` por sistema y build: una entrada solo para Windows 11 no aplica en Windows 10 y los límites son inclusivos. | unitario / negativo |
| `test_ediciones_filtra_home_y_pro`, `test_la_familia_filtra_...`, `test_familia_desconocida_...` | Filtrado por edición y por familia de Linux. | unitario / negativo |
| `test_entrada_con_binario_ausente_no_aplica` y relacionados (4) | Una entrada con un binario ausente (o no detectado) no aplica; con todos presentes sí. | negativo |
| `test_perfil_distinto_...`, `test_un_perfil_inexistente_...`, `test_los_privilegios_no_excluyen_...` | El perfil excluye; los privilegios no (quedan para `requiere_privilegios`). | unitario |
| `test_aplicabilidad_sobre_entradas_cargadas_desde_yaml` | `aplicable()` sobre una entrada leída de un YAML temporal (build, edición y sistema). | integración simulada |
| `test_en_windows_aparecen_las_25_herramientas` (Windows 10 Home, 11 Home y 11 Pro), `test_fuera_de_windows_el_esquema_queda_vacio`, `test_una_herramienta_solo_para_windows_11_...` | El esquema conserva las 25 herramientas en Windows y queda vacío en Linux y sistemas desconocidos; una herramienta solo para Windows 11 desaparece en Windows 10. | regresión / unitario |
| `test_en_linux_el_agente_no_envia_tools_...`, `test_en_windows_el_agente_envia_...` | En Linux el agente no envía `tools` (los proveedores rechazan un array vacío) y añade el aviso al system prompt; en Windows todo sigue igual. | integración simulada |

La equivalencia con P8 se mantiene: `test_esquema_equivale_semanticamente_al_de_p7` y `test_el_orden_de_las_herramientas_y_de_los_enums_tambien_se_conserva` siguen en verde sobre el Windows 11 simulado.

Comprobación de que los tests detectan fallos: se rompió temporalmente, una a una, la regla `build >= 22000`, el reconocimiento de `opensuse*`, la exclusión por binario ausente en `aplicable()`, el filtrado de `generar_tools_schema()` y la omisión de `tools` vacío en el agente; en los cinco casos algún test falló. El código se restauró después.

### Resultado
- Línea base antes de los cambios: **355 passed**.
- Tras P9: **454 passed** = 355 + 99 (`evidencias/P09_pytest.txt`). Sin fallos.
- `python -m src.plataforma` en el equipo de desarrollo (Windows 11, build 26300, edición `Core`, sin elevar): `evidencias/P09_capacidades_host.json`. El JSON no contiene usuario ni nombre del equipo.

### Cobertura de los módulos tocados
No medida: `pytest-cov` no está instalado en el entorno (ver P7).

### Pruebas manuales en VM
Ninguna en P9. La detección solo lee (registro, `os-release`, `/sys`) y los tests la simulan, pero **no se ha ejecutado en un Linux real**: las fixtures de os-release están escritas a partir del formato conocido de cada distribución, no copiadas de máquinas reales. Pendiente de Juan: ejecutar `python -m src.plataforma` en una VM Linux (p. ej. Ubuntu y Kali) y en Windows 10 y guardar la salida en `evidencias/vm/`.

## P10 — Entrega intermedia (2026-10-24)

Sin funcionalidad nueva: no se modifica ningún módulo de `src/` ni de `app/` ni ningún test. Se ejecuta la batería final con cobertura (`pytest-cov` instalado desde `requirements-dev.txt`) y se revisan secretos y datos personales.

### Resultado
- Línea base de la fase: **454 passed**. Tras P10: **454 passed**, 0 fallos, 0 errores, 0 omitidos, en 11,6 s (`evidencias/P10_pytest_final.txt`, `evidencias/P10_junit.xml`). Comando: `python -m pytest --cov=src --cov-report=term-missing --junitxml=docs/memoria/evidencias/P10_junit.xml`.
- Reproducibilidad: un clon limpio del repositorio, con un entorno virtual nuevo e `pip install -r requirements-dev.txt`, pasa también los 454 tests sin `.env` ni `logs/`. Las dependencias no tienen la versión fijada, así que se resolvieron versiones más recientes que las del entorno de desarrollo y la batería siguió en verde.
- Anonimización de las evidencias: el XML de JUnit incluye por defecto el nombre del equipo (`hostname=`) y la salida de pytest rutas absolutas; se sustituyeron por `anonimizado` y por rutas relativas / `<repo>`. Además, los identificadores de los 4 casos de `test_los_patrones_detectan_claves_falsas` incluyen las claves sintéticas del test y hacían saltar `test_ningun_fichero_contiene_claves` sobre el propio XML; se renombraron a `caso_sintetico_1…4`. Son las únicas ediciones manuales de esas salidas; el test de secretos no se ha modificado.

### Cobertura de `src/` (primera medición del proyecto)

| Módulo | Cobertura |
|---|---:|
| `src/catalogo.py` | 97 % |
| `src/tools_schema.py` | 100 % |
| `src/executor.py` | 95 % |
| `src/plataforma/` (3 ficheros) | 97,5 % (`deteccion.py` 97 %) |
| `src/agent.py` | 92 % |
| `src/audit.py` | 100 % |
| `src/config.py` | 70 % (`cargar_perfil()` sin tests, líneas 40-60) |
| **Total** | **96 %** (902 sentencias, 40 sin cubrir) |

Es cobertura de líneas y solo de `src/`; `app/` (incluida la vista de Streamlit) no se mide. Detalle de líneas no cubiertas en `DATOS_PARA_MEMORIA.md`.

### Seguridad
- `tests/test_repo_sin_secretos.py`: 10 de 10 en verde.
- `git log --all -G "gsk_[A-Za-z0-9]{10,}" --oneline`: sin coincidencias.
- Ningún fichero de `logs/`, `data/` ni `.env` versionado, ni en el índice ni en el historial; sin nombre de usuario, nombre de equipo, correos, IPs ni rutas personales en los ficheros versionados.

### Pruebas manuales en VM
Ninguna en P10. Siguen pendientes de Juan las de P2–P6, la repetición en la VM de una lectura y una acción con confirmación tras la migración al catálogo (P8) y `python -m src.plataforma` en una VM Linux y en Windows 10 (P9), con salida en `evidencias/vm/`.

## Validación específica del código generado por IA (borrador de P10)

Resumen de cómo se ha comprobado el código y la documentación generados por la IA (Claude Code), con lo que consta en el repositorio. Está sujeto a la confirmación del autor y a las pruebas en VM, que siguen pendientes.

### Controles aplicados

| Control | Qué comprueba | Dónde consta |
|---|---|---|
| Revisión humana del diff antes del commit | Que el autor entiende y acepta cada cambio; en P7–P10 consta como «Revisado y aceptado por el autor». | `REGISTRO_IA.md` |
| Tests con LLM y PowerShell simulados | Que el código se comporta como se espera sin ejecutar acciones reales. 454 tests, cobertura de `src/` del 96 %. | `evidencias/P10_pytest_final.txt` |
| Tests negativos y de la lista de denegación | Que se rechazan campos desconocidos, ids duplicados, enums inválidos y 24 tokens peligrosos en plantillas y en argv (48 casos). | `tests/test_catalogo.py` |
| Tests de inyección de prompts | Que el contenido malicioso en la salida de una herramienta no provoca ninguna acción sin confirmación (3 tests). | `tests/test_injection.py` |
| Instantáneas de regresión de la migración | Que en P8 el esquema, las plantillas, los niveles, los permisos de administrador y los timeouts de las 25 herramientas son idénticos a los de P7. Las instantáneas se generaron con el código anterior. | `tests/fixtures/schema_p7.json`, `whitelist_p7.json` |
| Comprobación de que los tests detectan fallos | Se rompió a propósito cada pieza clave (4 en P8, 5 en P9) y en los 9 casos algún test falló; después se restauró el código. | Secciones P8 y P9 de este documento |
| Test anti-secretos | Que no hay claves ni `.env` en el repositorio; además `git log --all -G "gsk_[A-Za-z0-9]{10,}"` no devuelve nada. | `tests/test_repo_sin_secretos.py` |
| Revisión de coherencia de la documentación | Contraste de los documentos de memoria entre sí y con el código. Detectó 4 errores documentales generados por IA. | `INCIDENCIAS_IA.md` (INC-01 a INC-04) |
| Verificación de los mapeos a marcos con fuentes oficiales | Contraste de las propuestas de la IA con attack.mitre.org, con el anexo II del Real Decreto 311/2022 y con CIS Controls v8.1. Detectó 2 errores (IDs de ATT&CK obsoletos y una medida del ENS mal asignada). | `INCIDENCIAS_IA.md` (INC-06 e INC-07); CIS Controls v8.1 contrastado sin errores |

### Errores o comportamientos incorrectos detectados y correcciones

Hay 7 incidencias registradas, todas en documentación o evidencias y ninguna en el código de `src/`; el detalle, con causa probable y corrección, está en `INCIDENCIAS_IA.md`. Hasta P9 no consta ninguna corrección del autor sobre el código generado.

### Límites de la validación (lo que no está comprobado)

- No hay pruebas reales en máquina virtual con resultado registrado: `evidencias/vm/` y `evidencias/capturas/` están vacías (procedimiento en `docs/demo_escenarios.md`). Las pruebas con efectos las lanza el autor (regla 17).
- La detección de plataforma en Linux solo se ha probado con ficheros `os-release` simulados, escritos de memoria por la IA a partir del formato de cada distribución, no copiados de máquinas reales. Tampoco se ha ejecutado en Windows 10.
- `cargar_perfil()` de `src/config.py` no tiene tests propios (cobertura de `config.py`: 70 %).
- La vista de Streamlit (`app/streamlit_app.py`) no tiene tests automáticos; `app/` no se incluye en la medición de cobertura.
- Los tests de inyección comprueban que el sistema no ejecuta nada sin confirmación, no si un modelo real «obedecería» el texto inyectado.
- Los mapeos a marcos cubren 14 de las 25 herramientas y tres marcos (CIS Controls v8.1, ATT&CK y ENS); CIS Benchmark, CCN-STIC y D3FEND no están mapeados (regla 15). Son orientativos, no una declaración de conformidad.
