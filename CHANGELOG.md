# Changelog

Historial de ProtexiumAI por fase, reconstruido a partir de `git log` y `git show --shortstat` (fechas y tamaños son los de cada commit). Las fases siguen la numeración del proyecto (P0–P10); los cuatro commits entre P6 y P7 se agrupan como «Post-P6». Los cambios respecto a la entrega preliminar, con su motivo, están en [`docs/memoria/CAMBIOS.md`](docs/memoria/CAMBIOS.md).

## P10 — Preparación de la entrega intermedia (2026-10-24 y 25)

Sin funcionalidad nueva. Las pruebas en máquina virtual se hicieron el 24 y 25 de octubre de 2026 y sus evidencias están en `docs/memoria/evidencias/vm/` y `capturas/`. Quedan como límites documentados de la entrega intermedia el mapeo a CIS Benchmark, CCN-STIC y D3FEND y el de las 11 herramientas sin mapeo en `catalogo/mapeo_marcos.csv` (solo valen los mapeos que verifique el autor, regla 15), y las limitaciones del modelo INC-11 e INC-12. El autor ha revisado el registro de herramientas de IA, el catálogo (áreas, sensibilidad y riesgo) y la planificación.

- `README.md` completo: requisitos, instalación, configuración, modo privado, ejecución, tests, estructura, aviso de pruebas en VM y limitaciones.
- Batería final: 458 tests en verde y cobertura de `src/` del 96 % (`docs/memoria/evidencias/P10_pytest_final.txt`, `P10_junit.xml`, regenerados tras las correcciones de la VM; la primera batería fue de 454).
- Nuevos documentos de memoria: `DATOS_PARA_MEMORIA.md` (cifras extraídas del repositorio) y `PLANIFICACION_RESTANTE.md` (planificación hasta junio de 2027, validada por el autor).
- Revisión de coherencia de `ESTADO_FUNCIONALIDADES.md`, `CAMBIOS.md` y `REGISTRO_IA.md` entre sí y con el código; las incoherencias halladas quedan listadas en `DATOS_PARA_MEMORIA.md`.
- Documentos de apoyo a la memoria: sección de validación del código generado por IA en `PRUEBAS.md`, estrategia de uso de la IA en `CAMBIOS.md`, doce incidencias en `INCIDENCIAS_IA.md` (INC-01 a INC-07 documentales, INC-08 a INC-12 de las pruebas en la VM) y mapeos de 14 herramientas a CIS Controls v8.1, ATT&CK y ENS, verificados por el autor, en `catalogo/mapeo_marcos.csv` (razonamiento y perfil en `catalogo/_mapeo_marcos_razonamiento.md`).
- Corrección hallada en las pruebas en la VM (INC-08): la salida de cada herramienta que se reenvía al LLM se recorta a 6.000 caracteres con aviso (`src/agent.py`), para no superar el límite de tokens del plan gratuito de Groq. 2 tests nuevos (456 en total).
- Pruebas en una máquina virtual con Windows 11: instalación desde cero, 458 tests, detección de plataforma, los tres escenarios de la demo (diagnóstico, alerta EICAR y refuerzo con confirmación y cancelación) y extracto de la auditoría, con capturas. Además de INC-08, INC-09 e INC-10, hallaron dos limitaciones del modelo sin corregir: INC-11 (valores numéricos en bruto) e INC-12 (fechas de las firmas de Defender).
- Test de plataforma independiente de la máquina (INC-09): el test de «no revela usuario ni equipo» usa nombres ficticios, porque con un equipo llamado `windows11` fallaba de forma espuria en la VM.
- Corrección de la codificación de la salida de PowerShell (INC-10): se decodifica con la página OEM de la consola en lugar de la ANSI, para que las tildes no lleguen corruptas al LLM ni a la auditoría (`src/executor.py`). 2 tests nuevos (458 en total).
- Revisión de seguridad: test de secretos en verde, historial sin claves `gsk_…`, ningún fichero de `logs/`, `data/` ni `.env` versionado, evidencias sin usuario ni nombre de equipo.

## P9 — Detección de plataforma y capacidades (commit `2f1723c`, 2026-10-24)

- Nuevo paquete `src/plataforma/` (F04): `Capacidades` (Windows por registro en solo lectura; Linux por `os-release` propio; binarios con `shutil.which`; AppArmor y SELinux), sin `subprocess`. `python -m src.plataforma` imprime el diagnóstico en JSON sin usuario ni nombre del equipo.
- `catalogo.aplicable()`: decide por sistema, build, edición, familia, binarios y perfil; los privilegios no excluyen una entrada.
- El esquema del LLM se filtra por equipo: 25 herramientas en Windows 10/11, ninguna en Linux. El agente no envía `tools` vacío y lo explica en el system prompt.
- 99 tests nuevos (454 en total), 10 fixtures de `os-release` y una fixture autouse en `tests/conftest.py` que simula un Windows 11 Pro.
- 27 ficheros, +1.534 −12 líneas.

## P8 — Catálogo YAML validado (commit `4b5c408`, 2026-10-24)

- Las 25 herramientas dejan de estar definidas en `src/executor.py` y pasan a `catalogo/herramientas_llm.yaml` (F03), cargado y validado por el nuevo `src/catalogo.py`: campos desconocidos, ids y claves duplicados, enums inválidos, marcadores sin declarar y lista de denegación (también tras expandir parámetros).
- `executor.WHITELIST` pasa a ser una vista derivada del catálogo; el esquema del LLM se sigue generando desde ella.
- Fusión de `catalogo/mapeo_marcos.csv` (vacío en P8; rellenado en P10): sin `verificado_por` un mapeo queda `verificado: false` (regla 15).
- Presupuesto de tokens: el esquema (~1.819 tokens) no puede superar 3.000.
- Sin cambio de comportamiento, comprobado con instantáneas de P7 (`tests/fixtures/schema_p7.json`, `whitelist_p7.json`). 160 tests nuevos (355 en total); se añade `pyyaml`.

## P7 — Línea base de la entrega intermedia (mismo commit `4b5c408`)

- Inventario del repositorio (`docs/memoria/estado_inicial.md`), plantillas de `docs/memoria/` y evidencias de la batería base (185 tests; 195 tras añadir los de secretos).
- `tests/test_repo_sin_secretos.py` (10 casos), `requirements-dev.txt` (`pytest-cov`), ajustes de `.gitignore` y `.env.example`, constante obsoleta de `scripts/hello_llm.py` corregida y reglas v2 (9–18) en `CLAUDE.md`.
- Sin cambios en `src/` ni `app/`.

## Post-P6 — 25 herramientas y rediseño de la interfaz (2026-09-01)

- `1aee76d` Amplía la WHITELIST de 7 a 25 herramientas, con tests y `docs/cobertura_windows_security.md` (+1.530 −6).
- `3d9b3cb` Incorpora el paquete de diseño de la interfaz, `design_handoff_protexiumai_ui/` (9 ficheros, +4.114). Es material de referencia, no código de producción.
- `4ae26e3` Módulos de apoyo de la interfaz: `app/textos.py`, `app/lecturas.py`, `app/auditoria.py`, `app/cliente_observado.py` y sus tests (+2.111).
- `26cbe3b` Reescribe la vista Streamlit según el rediseño: tema propio, `app/estilos.css`, semáforo de estado, tarjeta de permiso y pantallas de estado, auditoría y catálogo (+2.877 −156).

## P6 — Guion de demo y tests de inyección (`6d228a1`, 2026-08-28)

- `docs/demo_escenarios.md`: guion de la demo para la defensa.
- `tests/test_injection.py` (3 tests): el contenido de una herramienta nunca se ejecuta como instrucción sin confirmación humana.

## P5 — Modo privado con Ollama (`b22a112`, 2026-08-28)

- La auditoría registra el proveedor activo.
- `scripts/check_local.py` verifica Ollama y el modelo.
- Verificación de extremo a extremo con `llama3.2:3b` y sección de README (+143 −16).

## P4 — Interfaz Streamlit (`b87ba23`, 2026-08-28)

- `app/streamlit_app.py` con confirmación por botones (+339 −9).

## P3 — Agente conversacional y CLI (`76ffdcd`, 2026-08-28)

- `src/agent.py` (function calling, historial, system prompt), `src/tools_schema.py` (esquema generado desde la WHITELIST), `src/config.py` (perfiles groq/ollama) y `cli.py`; tests con el LLM simulado (+631).
- El modelo de Groq pasa a `openai/gpt-oss-20b` con `reasoning_effort="low"` (registrado en `docs/memoria/CAMBIOS.md`).

## P2 — Capa ejecutora (`6c3d8c2`, 2026-08-28)

- `src/executor.py` con WHITELIST de 7 herramientas, validación por enums, niveles y comprobación de administrador; `src/audit.py` (`logs/audit.jsonl`); `tests/test_executor.py` y `scripts/verificar_whitelist.py` (+689).

## P1 — Doble «hola mundo» (`7922ebd`, 2026-08-27)

- `scripts/hello_llm.py` y `scripts/hello_ps.py` (+145).

## P0 — Estructura inicial (`2728b9a`, 2026-08-27)

- Andamiaje: carpetas y módulos, `requirements.txt`, `.gitignore`, `.env.example` y `README.md` (16 ficheros, +162).
