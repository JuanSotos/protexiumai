# Estado de funcionalidades

Línea base: P7 (2026-10-22); actualizado en P8 (2026-10-23). Criterio de estado: existe en el repositorio y tiene tests = **completada**; hecha solo en parte = **en curso**; el resto = **pendiente**.
Origen: alumno / IA supervisada / software existente / mixto. Las funcionalidades existentes (F01, F02, F08, F12, F27) se marcan «IA supervisada» por indicación del autor (Claude Code, Sonnet 5.5, con revisión y decisiones de diseño del alumno; ver `REGISTRO_IA.md`).

| ID | Funcionalidad | Hito | Estado (completada / en curso / pendiente) | Origen (alumno / IA supervisada / software existente / mixto) | Evidencia (test, fichero, captura) |
|---|---|---|---|---|---|
| F01 | Conversación en lenguaje natural con agente LLM y function calling | H0 | completada | IA supervisada | `src/agent.py`, `cli.py`; `tests/test_agent.py` (16 tests); `tests/fixtures/schema_p7.json` |
| F02 | Proveedor LLM dual nube (Groq) / local (modo privado) | H0; motor integrado en H5 | en curso | IA supervisada | `src/config.py` (perfiles groq/ollama), `scripts/check_local.py`; la parte H0 existe pero `cargar_perfil()` no tiene tests propios y falta integrar el motor (H5) |
| F03 | Catálogo cerrado YAML con metadatos de marcos | H1 | completada | IA supervisada | `catalogo/` (`herramientas_llm.yaml` con las 25 herramientas, `_ESQUEMA.md`, `mapeo_marcos.csv`), `src/catalogo.py`; `tests/test_catalogo.py` (150 tests) y `tests/test_catalogo_regresion.py` (10 tests); `evidencias/P08_pytest.txt`. El CSV de marcos está vacío a propósito: los identificadores CIS/CCN/ATT&CK los aporta Juan con `verificado_por` (regla 15) |
| F04 | Detección de plataforma y capacidades | H1 | pendiente | — | — |
| F05 | Validador y política con listas de denegación | H1 | pendiente | — | — (hoy solo hay validación contra enums en `src/executor.py`) |
| F06 | Confirmación humana sobre un plan visible | H1 | pendiente | — | — (hoy la confirmación por botón existe en `src/agent.py` y está testeada en `tests/test_agent.py`, pero no va ligada a un plan) |
| F07 | Remediación reversible check/plan/apply/verify/rollback | H1 | pendiente | — | — |
| F08 | Auditoría JSONL con token de marcha atrás | H0 parcial; H1 | en curso | IA supervisada | `src/audit.py`, `tests/test_auditoria.py` (26 tests), auditoría en `tests/test_executor.py`; falta el token de marcha atrás (H1) |
| F09 | Perfiles Hogar / Sistemas | H1 configuración; H5 interfaces | pendiente | — | — |
| F10 | Enrutador por sensibilidad del dato y anonimizador | H1 | pendiente | — | — |
| F11 | Comprobaciones Windows 10/11 CIS nivel 1 (30–40) | H2 | pendiente | — | — |
| F12 | Integración Defender: escaneo, cuarentena y restauración | H0 parcial; H2 | en curso | IA supervisada | `catalogo/herramientas_llm.yaml` (antes en `src/executor.py`): `get_defender_status`, `get_detected_threats`, `start_quick_scan`, `start_full_scan`, `start_custom_scan`, `update_signatures`, `remove_all_threats`; `tests/test_executor.py` (99 tests); faltan cuarentena y restauración (H2) |
| F13 | HardeningKitty en modo Audit (opcional) | H2 | pendiente | — | — |
| F14 | Índice de configuración | H2 | pendiente | — | — |
| F15 | Auditoría Linux con Lynis | H3 | pendiente | — | — |
| F16 | ClamAV bajo demanda | H3 | pendiente | — | — |
| F17 | rkhunter (opcional) | H3 | pendiente | — | — |
| F18 | Comprobaciones nativas Linux por familia | H3 | pendiente | — | — |
| F19 | Procesos y persistencia con heurísticas y línea base | H4 | pendiente | — | — |
| F20 | Reputación por hash (CIRCL, MalwareBazaar, VirusTotal) | H4 | pendiente | — | — |
| F21 | Reglas YARA-X | H4 | pendiente | — | — |
| F22 | Puntuación tipo THOR y semáforo | H4 | pendiente | — | — |
| F23 | Priorización de parches KEV/EPSS e índice de exposición | H5 | pendiente | — | — |
| F24 | Interfaces Hogar/Sistemas completas e informes HTML con deriva | H5 | pendiente | — | — |
| F25 | Instalador Windows y paquetes Linux | H5 | pendiente | — | — |
| F26 | Evaluación en VMs y benchmark nube/local | H6 | pendiente | — | — |
| F27 | Tests de inyección de prompts | H0; se amplían en cada fase | en curso | IA supervisada | `tests/test_injection.py` (3 tests); se amplía en cada fase |
