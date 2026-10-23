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
