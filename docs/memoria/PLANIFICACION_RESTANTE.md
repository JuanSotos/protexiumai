# Planificación restante

> **Estado: validada por Juan el 2026-10-25.** La redactó la IA a partir del estado real del repositorio en P10 (2026-10-24) y de la memoria preliminar «Planteamiento final y estructura», cuya Tabla 5 fija las ventanas de cada hito. Supuestos confirmados por Juan: dedicación de **10 a 20 horas semanales**, **sin periodos de baja disponibilidad** que descontar (exámenes, prácticas, trabajo) y **fecha de defensa aún desconocida**. Con la fecha real se revisarán H6 y H7. El contraste con la Tabla 5 está en el apartado 4.
>
> **Ampliación del 2026-10-25: sustitución de la interfaz Streamlit.** Juan ha decidido reemplazar la interfaz de Streamlit por una aplicación web en React que hable con el agente mediante una API local en Python (agente, ejecutor, catálogo y auditoría no cambian). La decisión es de Juan; el reparto por hitos de los apartados 3.1, 3.2, 3.5 y 5 lo propuso la IA y **Juan lo validó el mismo día**, junto con tres puntos: el tiempo de F13 es el que se sacrifica si H2 no llega, la ventana de escritorio del instalador se decide en H5 (hasta entonces, navegador) y Streamlit se retira antes del 2027-04-16. Se registra en `CAMBIOS.md` (tabla 1).

## 1. Punto de partida (hechos del repositorio)

| Hito | Funcionalidades | Estado en P10 |
|---|---|---|
| H0 | F01, F02, F08 (parcial), F12 (parcial), F27 | Prototipo funcional en Windows 11: agente, executor con 25 herramientas, Streamlit, modo privado con Ollama, auditoría y 3 tests de inyección. F02, F08, F12 y F27 siguen «en curso». |
| H1 | F03–F10 | **Hecho:** F03 catálogo YAML validado (P8) y F04 detección de plataforma y capacidades (P9). **Pendiente:** F05 validador y política, F06 confirmación ligada al plan, F07 remediación reversible, F08 token de marcha atrás, F09 perfiles, F10 enrutador y anonimizador. |
| H2–H7 | F11–F26 | Todo pendiente. `catalogo/windows/` y `catalogo/linux/` están vacíos. |

Cifras de partida: 3 funcionalidades completadas, 4 en curso, 20 pendientes; 458 tests; cobertura de `src/` del 96 %; 25 herramientas en el catálogo y ninguna comprobación (`DATOS_PARA_MEMORIA.md`). P9, que la petición incluía «si no se hizo», **sí está hecha** (commit `2f1723c`), aunque falta contrastarla en una VM Linux real.

Capacidades ya disponibles sobre las que se construye: `catalogo.aplicable()` ya decide por sistema, build, edición, familia, binarios y perfil; el catálogo ya admite los motores `powershell`, `registro`, `comando` y `python` y los tipos `comprobacion` y `accion`, aunque solo se usa `herramienta`; el esquema del LLM está limitado a 3.000 tokens y las futuras comprobaciones deben agruparse por área.

## 2. Calendario propuesto

Se respeta la ventana de cada hito de la Tabla 5 de la memoria preliminar. Como la propia tabla, el calendario **solapa** hitos consecutivos; el solape solo es viable si el trabajo avanza al ritmo de P7–P9 (tres fases entre el 22 y el 24 de octubre) y si las pruebas en VM de Juan no se acumulan. La fecha de la defensa **todavía no se conoce**: el cierre del 18 de junio de 2027 es el de la ventana de la memoria preliminar y se sustituirá por la real cuando se sepa.

| Hito | Ventana en la Tabla 5 | Inicio | Fin | Dentro de la ventana |
|---|---|---|---|---|
| H1 resto | Oct.–nov. 2026 | 2026-10-26 | 2026-11-30 | Sí |
| H2 | Nov. 2026–ene. 2027 | 2026-11-23 | 2027-01-29 | Sí |
| H3 | Dic. 2026–feb. 2027 | 2027-02-01 | 2027-02-26 | Sí |
| H4 | Feb.–mar. 2027 | 2027-02-15 | 2027-03-31 | Sí |
| H5 | Mar.–abr. 2027 | 2027-03-22 | 2027-04-30 | Sí |
| H6 | Abr.–may. 2027 | 2027-04-19 | 2027-05-21 | Sí |
| H7 | May.–jun. 2027 | cierre 2027-05-17 (redacción continua desde 2026-11) | 2027-06-18 (provisional hasta conocer la fecha de la defensa) | Sí |

Solapes: H1/H2 una semana, H2/H3 ninguno (por decisión de Juan, dada su dedicación de 10 a 20 horas semanales), H3/H4 y H5/H6 dos semanas, H4/H5 algo más de una y H6/H7 una. H2 atraviesa las vacaciones de Navidad, sin descontar semanas por indicación de Juan. Sin solape, H3 queda en unas cuatro semanas para sus cuatro funcionalidades, por lo que F17 (opcional) es la primera que se sacrifica. Si el ritmo real de H1 no alcanza el 30 de noviembre, se retrasa el inicio de H2 y se acorta H3 (con F17 fuera) antes que recortar H6 y H7.

Orden de sacrificio si el ritmo real no alcanza: primero F17 (H3) y F13 (H2), ambas opcionales. La migración de la interfaz no se recorta dentro de H2 sino que se aplaza: mientras React no iguale a Streamlit en las pantallas de chat, confirmación y estado, **Streamlit sigue siendo la interfaz de la demo**, así que un retraso no deja el proyecto sin interfaz. Fecha límite para retirar Streamlit: **2027-04-16**, antes de empezar H6, que es cuando se sacan las capturas de la evaluación.

La memoria (H7) no se deja para el final: cada hito termina con las evidencias de la regla 16 (REGISTRO_IA, ESTADO_FUNCIONALIDADES, PRUEBAS, CAMBIOS y salida de pytest) y `DATOS_PARA_MEMORIA.md` se regenera al cerrar cada uno.

## 3. Detalle por hito

### 3.1 H1 resto — del 26 de octubre al 30 de noviembre de 2026

Objetivo: terminar la capa de seguridad y gobierno antes de añadir comprobaciones, porque H2–H4 dependen de ella.

| Bloque (fase propuesta) | Funcionalidad | Trabajo | Criterio de aceptación |
|---|---|---|---|
| P11 Validador y adaptadores por SO | F05 | Política de validación sobre el catálogo (hoy solo hay validación por enums y lista de denegación en la carga): validar cada llamada en tiempo de ejecución, y adaptadores por motor y sistema (`powershell` con `-NoProfile -NonInteractive` y sin ventana, `registro` con `winreg` de solo lectura, `comando` con `shell=False`, ruta absoluta de `shutil.which`, entorno mínimo y *timeout*; reglas 10 y 11). | Ningún comando se construye fuera de los adaptadores; test que lo demuestre; sin `sudo`/`su`/`pkexec`/`doas`. Un binario ausente da `no_aplicable`, nunca excepción (regla 14). |
| P12 Remediación reversible | F07, F06, F08 | Ciclo check/plan/apply/verify/rollback sobre el tipo `accion`; plan visible y confirmación **ligada al plan mostrado** (regla 12); token de marcha atrás en la auditoría. Se empieza por las 4 mutantes actuales (firewall) como primer caso. | Una acción sin plan confirmado no se ejecuta; tests de que cambiar el plan invalida la confirmación; rollback probado en VM (lo lanza Juan, regla 17). |
| P12 (parte independiente de la interfaz) | F06 | Definir el contrato entre el agente y cualquier interfaz: eventos del turno (pensando, propuesta, ejecutando, resultado, error) y el plan con su identificador, al que va ligada la confirmación. Extraer la lógica del turno (hoy `EstadoTurno`, `_confirmar` y el hilo trabajador de `app/streamlit_app.py`) a un módulo sin dependencia de Streamlit y con tests. Streamlit pasa a consumir ese módulo. | La lógica del turno tiene tests propios y `streamlit_app.py` no la contiene. Estimación: 2–3 días dentro de F06. Es lo único de la migración que entra en H1. |
| P13 Perfiles | F09 (configuración) | Perfiles `hogar` y `sistemas` en la configuración y en el filtrado del catálogo (el campo y `aplicable()` ya existen). | Mismas herramientas con distinta presentación y distinto filtrado; las interfaces completas quedan para H5. |
| P14 Enrutador y anonimizador | F10 | Enrutador por sensibilidad del dato (`router.py`, como en el apartado 4 de la memoria; el campo `sensibilidad` ya está en el catálogo): lo `personal` se procesa en local o pasa por el anonimizador (`anonimizador.py`) antes de salir a la nube. Decisión de Juan para `get_allowed_firewall_rules`: en el perfil `sistemas` es técnica y en `hogar` es personal, con opción del usuario para revelar los nombres de las aplicaciones (hoy el catálogo la marca `personal`). | Tests con datos personales sintéticos: nunca llegan al cliente de Groq; el proveedor local los recibe. |
| Cierre | F27, F02 | Ampliar `tests/test_injection.py` (hoy 3 tests) con inyección en las salidas nuevas; tests de `cargar_perfil()` (hoy sin ellos). | Cierra la incoherencia I-7 y el 70 % de `config.py`. |

Dependencias de Juan: revisar el reparto de áreas/sensibilidad/riesgo de P8, completar `mapeo_marcos.csv` (CIS Benchmark, CCN-STIC, D3FEND y las 11 herramientas sin mapeo), y lanzar en VM las pruebas con efectos y la detección en Linux/Windows 10 pendientes de P9.

### 3.2 H2 — Núcleo Windows 10/11 — del 23 de noviembre de 2026 al 29 de enero de 2027

| Funcionalidad | Trabajo | Notas |
|---|---|---|
| F11 | 30–40 comprobaciones CIS nivel 1 en `catalogo/windows/*.yaml` (tipo `comprobacion`, motores `registro` y `powershell`, estados normalizados). | Los mapeos CIS/CCN/ATT&CK los aporta Juan con `verificado: true`; la IA solo propone (regla 15). |
| Agrupación por área | Exponer al LLM las comprobaciones por área (`cuentas`, `red`, `defender`, `dispositivo`, `sistema`, `actualizaciones`, `malware`), no una a una. | Mantener el esquema bajo 3.000 tokens (test existente). |
| F12 | Completar la integración con Defender: cuarentena y restauración. | Tamper Protection impide `Set-MpPreference`; se actúa por las vías permitidas. Requiere VM. |
| F13 | HardeningKitty en modo Audit (opcional: solo si sobra tiempo). | Dependencia externa: valorar licencia y si se instala o se documenta. |
| F14 | Índice de bastionado. | Se calcula a partir de severidad y peso ya definidos en el esquema. |
| Interfaz (sustituye a Streamlit; sin ID propio, entra en F24) | API local en Python (framework por decidir al empezar H2; escuchando solo en 127.0.0.1) y esqueleto en React con tres pantallas: chat, tarjeta de confirmación y estado del equipo. | Del 23/11 al 29/01. Se hace con el tiempo de F13, que es opcional. **Streamlit queda congelado**: solo correcciones, sin pantallas nuevas. La API exige token de sesión, comprobación de `Origin`/`Host` y confirmación ligada al identificador del plan; no ejecuta nada por sí misma (regla 1). Tests negativos: sin token, `Origin` falso, plan distinto del propuesto. Dependencias nuevas (framework de la API, por decidir al empezar H2, y cadena de Node) por justificar y fijar con versión exacta. |

Criterio de cierre: Windows 10 y 11 (Home y Pro) probadas en VM; cobertura de `src/` ≥ 90 %.

### 3.3 H3 — Núcleo Linux — del 1 al 26 de febrero de 2027

| Funcionalidad | Trabajo |
|---|---|
| F15 | Auditoría con Lynis. |
| F16 | ClamAV bajo demanda. |
| F17 | rkhunter (opcional: solo si sobra tiempo). |
| F18 | Comprobaciones nativas por familia (debian, rhel, arch, suse) en `catalogo/linux/*.yaml`. |

Primero, ejecutar `python -m src.plataforma` en VMs reales (Ubuntu, Debian, Fedora o Rocky, Kali) y guardar la salida en `evidencias/vm/`: la detección de P9 solo se ha probado con ficheros simulados. Después, adaptadores Linux con `subprocess` en lista, `shell=False` y entorno fijo. El agente deja de enviar un esquema vacío en Linux.

### 3.4 H4 — Procesos y persistencia — del 15 de febrero al 31 de marzo de 2027

| Funcionalidad | Trabajo |
|---|---|
| F19 | Procesos y persistencia con heurísticas y línea base. |
| F20 | Reputación por hash (CIRCL, MalwareBazaar, VirusTotal). Atención al enrutador de F10: solo hashes, nunca contenido ni rutas. |
| F21 | Reglas YARA-X. |
| F22 | Puntuación tipo THOR y semáforo. |

Claves de VirusTotal y similares: solo en `.env`, nunca en el repositorio (regla 8); el test de secretos sigue siendo la barrera.

Interfaz: todo lo que se vea en pantalla a partir de H2 (resultados de F11 en H2, índice de F14, puntuación y semáforo de F22) se construye **solo en React**, para no hacerlo dos veces. El backend entrega a la API datos ya preparados en lenguaje llano (los módulos `app/textos.py` y `app/lecturas.py` se conservan, con sus tests).

### 3.5 H5 — Priorización, interfaces, instaladores y motor local — del 22 de marzo al 30 de abril de 2027

| Funcionalidad | Trabajo |
|---|---|
| F23 | Priorización de parches con KEV y EPSS e índice de exposición. |
| F24 | Interfaces Hogar y Sistemas completas e informes HTML con deriva, **en React** sobre el esqueleto de H2 (pantallas restantes: catálogo, auditoría, detalle del equipo y los dos perfiles). Hoy la vista de Streamlit es la rediseñada en Post-P6 y no tiene tests automáticos. Retirada de Streamlit antes del 2027-04-16 y de `streamlit` en `requirements.txt`. |
| F25 | Instalador de Windows y paquetes de Linux. Empaquetan el build estático de React junto a la API; decidir entonces si se abre en el navegador o en una ventana propia (pywebview o Tauri), valorando que en Linux haga falta WebKitGTK. |
| F02 (resto) | Motor local integrado con `llama-cpp-python`, para no depender de Ollama aparte. |

Riesgo: comprobar con tiempo que `llama-cpp-python` se instala en las versiones de Python y de sistema objetivo (ruedas precompiladas o compilación); si no, el plan B, confirmado por Juan, es mantener Ollama como motor local, documentarlo y registrarlo en `CAMBIOS.md` como cambio de alcance.

### 3.6 H6 — Evaluación — del 19 de abril al 21 de mayo de 2027

F26: evaluación en VMs (Windows 10/11 y distribuciones de H3) y *benchmark* nube/local (acierto de herramienta, validez de argumentos, tokens y latencia), repitiendo con las herramientas actuales la verificación de P5, que solo se hizo con 7 herramientas y `llama3.2:3b`. Resultados y capturas en `evidencias/vm/` y `evidencias/capturas/`.

### 3.7 H7 — Memoria y defensa — cierre del 17 de mayo al 18 de junio de 2027

Memoria completa a partir de `docs/memoria/`, regeneración de `DATOS_PARA_MEMORIA.md`, ensayos con el snapshot «Demo lista» (`docs/demo_escenarios.md`) y defensa. La fecha de la defensa aún no se conoce; las últimas semanas hasta ella son colchón.

## 4. Contraste con la Tabla 5 de la memoria preliminar

Fuente: «Planteamiento final y estructura» (Juan Sotos Ossorio, 2026/2027), Tabla 5 y los apartados 2–7. Se ha leído entera y se ha comparado con el repositorio.

### 4.1 Hitos

| Hito | Contenido en la Tabla 5 | Estado real (2026-10-24) | ¿Desviación? |
|---|---|---|---|
| H0 ✓ (hasta sep. 2026) | Prototipo en Windows 11: 25 herramientas, agente, interfaz y 185 tests | Cumplido: 25 herramientas, agente, Streamlit y exactamente 185 tests en la línea base P7 | No |
| H1 (oct.–nov. 2026) | Catálogo con marcos (CIS, CCN), detección de plataforma, patrón plan/aplicar/deshacer y enrutador | Catálogo validado y detección de plataforma hechos (F03, F04); el CSV de marcos está vacío; plan/aplicar/deshacer y enrutador pendientes | No, pero con riesgo: quedan 2 de los 4 contenidos y 5 semanas |
| H2–H7 | Ventanas de nov. 2026 a jun. 2027 | No iniciados | No: la propuesta del apartado 2 cae dentro de cada ventana |

Tampoco hay desviación de plataformas: la memoria prevé probar en Windows 11 y 10, Ubuntu, Kali y Debian, y hoy solo hay pruebas reales en Windows 11; el resto es trabajo pendiente de H2/H3, no un cambio de alcance.

### 4.2 Cambios del repositorio que se habían marcado como posibles desviaciones

| Hecho en el repositorio | Qué dice la memoria | Veredicto |
|---|---|---|
| WHITELIST de 7 a 25 herramientas | Tabla 5, H0: «25 herramientas» | **No es desviación** |
| Rediseño de la interfaz Streamlit con un paquete de diseño | H0 incluye la interfaz; la Tabla 3 cita Claude Design / Figma para la interfaz | **No es desviación** |
| Modelo de Groq `openai/gpt-oss-20b` con `reasoning_effort="low"` | Apartado 4: «Nube: Groq con openai/gpt-oss-20b» | **No es desviación** frente a la memoria (en `CAMBIOS.md` figura en «Decisiones de diseño»: compara con el `CLAUDE.md` original, que citaba otro modelo) |
| WHITELIST en código pasa a catálogo YAML | Estructura por capas: «Catálogo YAML»; «esquema generado automáticamente desde el catálogo» | **No es desviación** frente a la memoria (en `CAMBIOS.md` figura en «Decisiones de diseño»: compara con el prototipo H0) |
| Esquema del LLM filtrado por las capacidades del equipo | Apartado 4: `tools_schema.py` «filtradas según lo que existe en el equipo» | **No es desviación** |
| Orden interno de H1 (F03 y F04 antes que el resto) | La Tabla 5 no fija orden | **No es desviación** |
| Comprobaciones agrupadas por área en el esquema del LLM | No lo menciona | **Desviación de diseño menor**: refinamiento por el límite de tokens de Groq; ya en la tabla 1 de `CAMBIOS.md` |
| Sustitución de Streamlit por React con API local (decisión de Juan, 2026-10-25) | H0 incluye «la interfaz» y F24 «interfaces Hogar/Sistemas completas»; la Tabla 3 cita Claude Design / Figma. **Comprobado por Juan (2026-10-25): la preliminar nombra Streamlit** en el apartado 6 (capa 1 de la estructura) y en el apartado 7 (librerías) | **Cambio de tecnología respecto a la preliminar, no de alcance**: F24 y su hito no cambian. Registrado en la tabla 1 de `CAMBIOS.md`. Justificación apoyada en el diseño de Claude Design (HTML) y en la falta de tests de la vista; no se afirma que Streamlit sea lento sin medirlo |
| Reglas de seguridad v2 (9–18) en `CLAUDE.md` | Apartado 3: «ocho reglas de seguridad obligatorias» | **Diferencia de estrategia**: las 8 siguen vigentes y se añaden 10; registrada en la tabla 1 de `CAMBIOS.md` |

### 4.3 Cifras de la memoria que han quedado desfasadas

La memoria cita «185 actualmente» (tests, apartado 3), que hoy son **458**, y «ocho reglas» (ahora 18). No son desviaciones y no hace falta modificarla: es la versión de la entrega de planteamiento y la memoria de la entrega intermedia recogerá las cifras actuales.

### 4.4 Conclusión

No hay desviaciones de calendario ni de alcance respecto a la Tabla 5. Solo tres diferencias de diseño o de tecnología (agrupación por área, reglas v2 y sustitución de la interfaz Streamlit por React), todas recogidas en la tabla 1 de `CAMBIOS.md`.

## 5. Riesgos

| Riesgo | Efecto | Mitigación propuesta |
|---|---|---|
| Plan gratuito de Groq (8.000 tokens/min) | El esquema crece con las comprobaciones. | Agrupar por área; test de 3.000 tokens ya existente; medir con el tokenizador real en H6. |
| Pruebas con efectos solo en VM y las lanza Juan (regla 17) | La validación en Linux, Windows 10 y rollback puede retrasar cada hito. | Pedir a Juan una tanda de pruebas por hito, con guion y lista de evidencias a guardar. |
| Tamper Protection y antivirus de terceros | Algunas remediaciones de Defender no son posibles. | Diseñar los estados `requiere_privilegios` y `no_aplicable` y explicarlos en lenguaje llano. |
| Modelo local pequeño | Peor elección de herramientas y narración. | Benchmark en H6; el estado real siempre sale de la auditoría, no de la narración. |
| Mapeos a marcos verificados solo por Juan | Bloquea la columna de marcos de H2/H3. | Trabajo por lotes durante H1; la IA propone con `verificado: false`. |
| Dependencias externas (HardeningKitty, Lynis, rkhunter, YARA-X, llama-cpp-python) | Licencias, versiones y disponibilidad. | Marcarlas opcionales donde el plan lo permite y registrar en `CAMBIOS.md` cualquier sustitución. |
| Dependencias sin versión fijada | Una actualización puede romper la instalación. | Fijar versiones antes de los instaladores (H5). Con la nueva interfaz se suman el framework de la API (por decidir al empezar H2) y el árbol de paquetes de Node: lockfile y versiones exactas desde el primer día de H2. |
| API local de la nueva interfaz | Una web maliciosa abierta en el navegador podría enviar peticiones a `localhost` e intentar confirmar una acción. | Escucha solo en 127.0.0.1, token de sesión, comprobación de `Origin`/`Host`, sin CORS abierto y confirmación ligada al identificador del plan (regla 12). Tests negativos para cada caso. La regla 19 de `CLAUDE.md`, aprobada por Juan el 2026-10-25, recoge estas medidas. |
| Migración de la interfaz en H1/H2 sin holgura | Quita tiempo a la capa de seguridad, de la que dependen H2–H4. | Solo el contrato entra en H1 (2–3 días dentro de F06); el resto va en H2 con el tiempo de F13. Streamlit sigue siendo la interfaz hasta que React la iguale. |
| Fecha de la defensa desconocida | H6 y H7 podrían tener que adelantarse. | Revisar la planificación en cuanto se conozca la fecha; el colchón de H7 es la reserva. |
