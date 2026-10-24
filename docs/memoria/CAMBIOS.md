# Cambios respecto a la entrega preliminar

Referencia: la memoria preliminar «Planteamiento final y estructura» (Tabla 5 de hitos). Revisada en P10: el calendario y el alcance de H0 (25 herramientas, agente, interfaz y 185 tests) se cumplen sin desviaciones (ver `PLANIFICACION_RESTANTE.md`, apartado 4). Esa memoria no se modifica: la siguiente es la de la entrega intermedia.

El documento tiene dos tablas. La primera recoge lo que se aparta de la memoria preliminar. La segunda recoge decisiones de diseño tomadas durante el desarrollo que **no** se apartan de ella (la memoria ya describe el modelo `openai/gpt-oss-20b`, el catálogo YAML y el esquema filtrado por equipo) pero sí del `CLAUDE.md` y del código originales del prototipo.

## 1. Cambios respecto a la memoria preliminar

| Ámbito (planificación / alcance / arquitectura / tecnologías / estrategia de IA) | Cambio respecto a la entrega preliminar | Motivo | Impacto | Fase |
|---|---|---|---|---|
| arquitectura | Las futuras comprobaciones no se expondrán una a una al LLM, sino agrupadas por área (`cuentas`, `red`, `defender`, `dispositivo`, `sistema`, `actualizaciones`, `malware`). | Cada herramienta expuesta añade tokens al esquema que se envía en cada llamada, y el plan gratuito de Groq limita a 8.000 tokens por minuto. El esquema actual de 25 herramientas ocupa unos 1.819 tokens. | `tests/test_catalogo_regresion.py` falla si el esquema supera los 3.000 tokens. Las comprobaciones de H2/H3 vivirán en el catálogo (`windows/`, `linux/`) con tipo `comprobacion` y no entrarán en el esquema del LLM hasta que se diseñe su agrupación por área. | P8 |
| estrategia de IA | Las reglas de seguridad de `CLAUDE.md` pasan de 8 a 18: se mantienen las 8 originales y se añaden las reglas 9–18 (catálogo como única fuente de verdad, ejecución en Linux y Windows, plan/confirmación ligada, estados normalizados, mapeos a marcos verificados, evidencias y pruebas solo en VM). | La memoria preliminar (apartado 3) cita «ocho reglas de seguridad obligatorias». Las nuevas reglas concretan el diseño multiplataforma y la trazabilidad del TFG sin relajar ninguna de las originales. | Cambia `CLAUDE.md`. La memoria de la entrega intermedia recoge las 18 reglas. | P7 |

## 2. Decisiones de diseño durante el desarrollo

Cambios respecto al `CLAUDE.md` y al código originales del prototipo (H0). Son coherentes con la memoria preliminar, que ya los plantea; se documentan por su motivo y su impacto.

| Ámbito | Cambio respecto a | Cambio | Motivo | Impacto | Fase |
|---|---|---|---|---|---|
| tecnologías | `CLAUDE.md` original (modelo `llama-3.3-70b-versatile`). La memoria preliminar ya indica `openai/gpt-oss-20b`. | El modelo del proveedor en la nube pasa de `llama-3.3-70b-versatile` a `openai/gpt-oss-20b`, y las llamadas al proveedor `groq` (solo a ese) llevan `reasoning_effort="low"`. | Groq retiró `llama-3.3-70b-versatile` de su catálogo. Los modelos con function calling que quedan son de razonamiento y, sin limitar el esfuerzo, reservan tokens que superan el límite por minuto del tier gratuito. | Cambia el modelo en `src/config.py` (`GROQ_MODELO`) y se añade un parámetro específico de groq en `src/agent.py`; el proveedor local (Ollama) no cambia. El cambio de código es anterior a P7 (commit `76ffdcd`); en P7 se registra aquí, se aclara `.env.example` y se corrige la constante obsoleta de `scripts/hello_llm.py`. | P3 (código); P7 (registro) |
| arquitectura | Prototipo H0 (WHITELIST en código en `src/executor.py`). La memoria preliminar ya plantea un catálogo YAML (capa 4). | La WHITELIST definida en código pasa a ser un catálogo YAML validado (`catalogo/herramientas_llm.yaml`, cargado por `src/catalogo.py`). `executor.WHITELIST` se conserva como vista derivada del catálogo y `src/tools_schema.py` genera el esquema desde ella. | El prototipo H0 definía las herramientas en una WHITELIST en código. Las comprobaciones multiplataforma (Windows/Linux, CIS, marcos normativos) necesitan metadatos (plataforma, privilegios, severidad, marcos) y validación estricta que no caben en un diccionario Python; además el catálogo es revisable sin leer código. | Se añaden `catalogo/` y `src/catalogo.py` y la dependencia PyYAML. El comportamiento de las 25 herramientas no cambia (comprobado con instantáneas de P7: esquema, plantillas, niveles, administrador y timeouts) y la batería previa pasa sin modificar sus asserts. Si el catálogo no valida, la aplicación no arranca. | P8 |
| arquitectura | Prototipo H0 (esquema del LLM fijo). La memoria preliminar ya plantea un esquema «filtrado según lo que existe en el equipo» (apartado 4). | El esquema de herramientas que recibe el LLM deja de ser fijo: `generar_tools_schema()` solo incluye las herramientas que `catalogo.aplicable()` da por válidas para las capacidades detectadas del equipo (`src/plataforma/`). En un equipo sin herramientas aplicables (Linux, hasta H3) el agente no envía `tools` y avisa en el system prompt. | Los módulos Windows/Linux de H2 y H3 conviven en un mismo catálogo; ofrecer al LLM una herramienta que no puede ejecutarse en el equipo produciría errores y gastaría tokens (límite de 8.000/min de Groq). Los proveedores además rechazan un array `tools` vacío. | Se añade el paquete `src/plataforma/`, la función `aplicable()` y el parámetro opcional `capacidades` en `Agent`. En Windows 10/11 el esquema es idéntico al de P8 (25 herramientas, test de equivalencia en verde). `tests/conftest.py` gana una fixture autouse que simula un Windows 11 Pro para que la batería no dependa del equipo. | P9 |

## 3. Estrategia de uso de la IA: límites, cambios y herramientas (borrador)

Recoge lo que consta en el repositorio; los motivos son los que se deducen de él y el autor debe confirmarlos. Los apartados marcados «pendiente del autor» solo los puede completar Juan.

### 3.1 Cambios en la estrategia

| Cambio | Motivo | Impacto | Fase |
|---|---|---|---|
| La IA propone y el humano decide: confirmación obligatoria para toda herramienta de acción o mutante, y los mapeos a marcos solo valen si los verifica el autor (`verificado: false` por defecto). | Una IA puede equivocarse o inventar identificadores; en seguridad, un fallo tiene efectos reales. | Reglas 3, 12 y 15 de `CLAUDE.md`; el cargador del catálogo rechaza un mapeo sin `verificado_por`. | P2; P8 |
| Las pruebas con efectos sobre el sistema las lanza el autor en máquinas virtuales; la IA solo ejecuta tests simulados y lecturas inocuas. | La IA no debe modificar el equipo de desarrollo y no puede validar por sí sola el comportamiento real. | Regla 17; las evidencias de VM dependen del autor y siguen pendientes. | P7 |
| Mayor automatización del desarrollo: de fragmentos y módulos con revisión (N2–N3) en P0–P6 a desarrollo agéntico por fase (N4) en P7–P10, con plantillas de evidencias, instantáneas de regresión y revisión del diff por el autor. | Las fases de la entrega intermedia son amplias y verificables con tests; la revisión humana se concentra en el diff y en las decisiones de diseño. | Más trazabilidad (`REGISTRO_IA.md`, `INCIDENCIAS_IA.md`, `PRUEBAS.md`). | P7 |
| Cambio de modelo de Claude Code según la fase: Sonnet 5 en P0–P6, Opus 5 en tres de los commits posteriores a P6 y Sonnet 5.5 en P7–P10. | No registrado en el repositorio (pendiente del autor). | Se refleja en `REGISTRO_IA.md`. | Varias |

### 3.2 Límites encontrados

| Límite | Evidencia en el repositorio | Consecuencia |
|---|---|---|
| El plan gratuito de Groq limita a 8.000 tokens por minuto y retiró el modelo previsto. | Comentario de `src/config.py` y tabla 2 de este documento. | Se usa `openai/gpt-oss-20b` con `reasoning_effort="low"`; el esquema de herramientas no puede superar 3.000 tokens, de ahí la agrupación por área. |
| Un modelo local pequeño (`llama3.2:3b`) falla algunas veces: en la verificación de P5, 13 de 14 llamadas fueron válidas y el fallo lo frenó el validador. Además, narra mal el resultado de una acción cancelada. | `README.md` (modo privado) y `PRUEBAS.md`, P5. | La interfaz muestra aparte el estado real de cada herramienta y `logs/audit.jsonl` es la fuente de verdad; la verificación no se ha repetido con las 25 herramientas. |
| La IA genera datos de prueba que no son datos reales. | Los 10 ficheros de `tests/fixtures/os-release/` están escritos de memoria. | La detección de Linux no se considera contrastada hasta probarla en una VM real. |
| Errores en documentación generada por IA que solo salen al contrastarla con el código o con las fuentes oficiales; en las propuestas de mapeo, identificadores de ATT&CK obsoletos y una medida del ENS mal asignada. | `INCIDENCIAS_IA.md`, INC-01 a INC-04, INC-06 e INC-07. | Se añade la revisión de coherencia al cierre de cada fase y la verificación humana de los identificadores de marcos (regla 15). |
| Un parte de pruebas generado puede volcar datos del equipo. | INC-05. | Las evidencias se anonimizan antes de guardarlas; el test de secretos las vigila. |
| Cobertura desigual de lo generado: la vista de Streamlit no tiene tests y `config.py` está al 70 %. | `PRUEBAS.md`, P10. | Mejoras previstas para H1. |

### 3.3 Herramientas y tareas

- **Descartadas o abandonadas:** pendiente del autor. No consta en el repositorio ninguna herramienta de IA descartada.
- **Tareas en las que la IA no ha resultado útil:** pendiente del autor. Lo que consta es que no puede, por diseño, verificar identificadores de marcos ni ejecutar las pruebas en VM.
- **Otras herramientas usadas fuera de Claude Code** (Claude (Opus) para arquitectura y documentación, Claude Design / Figma para la interfaz, según la memoria preliminar): pendiente del autor, que debe aportar fechas y grado de automatización para `REGISTRO_IA.md`.
