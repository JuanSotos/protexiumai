# Handoff: rediseño de la interfaz de ProtexiumAI

## Overview
ProtexiumAI es un asistente de seguridad conversacional para Windows 11 dirigido a usuarios domésticos sin conocimientos técnicos. El usuario pregunta en lenguaje natural y un LLM con function calling dispara comandos de PowerShell de una whitelist cerrada (`src/executor.py`). Este paquete contiene el rediseño de la interfaz: paleta y tipografía propias, modo claro y oscuro, y un tratamiento explícito del momento de confirmación humana.

Repositorio de origen: `JuanSotos/protexiumai` (rama `master`). La UI actual vive en `app/streamlit_app.py` y usa la plantilla por defecto de Streamlit.

## About the Design Files
Los archivos de este paquete son **referencias de diseño hechas en HTML**: prototipos que muestran el aspecto y el comportamiento deseados, no código de producción para copiar y pegar. La tarea es **recrear estos diseños en el entorno real del proyecto** (Streamlit + Python), respetando la arquitectura existente: `app/streamlit_app.py` para la vista, `src/agent.py` para el turno, `src/executor.py` para la whitelist y los niveles, `src/audit.py` para el registro.

En Streamlit esto significa, en orden de preferencia:
1. Inyectar un tema y CSS propios (`.streamlit/config.toml` para base/primaryColor/backgroundColor/textColor + un bloque `st.markdown("<style>…", unsafe_allow_html=True)` cargado desde un archivo `app/estilos.css`).
2. Sustituir los componentes que no admiten estilo suficiente (la tarjeta de propuesta, el semáforo, el recibo del turno) por HTML propio renderizado con `st.markdown(..., unsafe_allow_html=True)`, dejando en Streamlit solo los `st.button` que necesitan callback.
3. No cambiar la lógica del agente ni de la whitelist. La UI solo cambia de aspecto y de redacción.

Si en algún momento se decide abandonar Streamlit, el destino natural de estos diseños es una app web (React o similar) con el backend Python expuesto por API; el HTML de este paquete es directamente traducible.

> **Estado del paquete (31 · VIII · 2026).** La whitelist del proyecto pasó de 7 a **25 herramientas**;
> toda referencia a "7 herramientas" en este documento queda corregida por esa cifra. Lo nuevo de esa
> ampliación —pantallas de Estado en detalle, Auditoría, Catálogo, Ejecutando y Fallos del sistema, más
> las revisiones de la tarjeta de permiso— está especificado en `ADDENDUM-02-25-herramientas.md`.
> Léelo junto a este README: cuando los dos digan cosas distintas, manda el ADDENDUM-02.

## Cambios desde la primera entrega
1. **Tema claro atenuado.** Se abandona el blanco de Fluent: fondo `#DADAD8`, panel `#D2D2D0` (más oscuro que el fondo, no más claro), superficie `#E0E0DE`, texto `#292928` y secundario `#6B6B69`. Menos contraste, mismo carácter de modo claro.
2. **Azules de acento más saturados.** Claro `#0A6DD6` (antes `#005FB8`), oscuro `#5CC8FF` (antes `#60CDFF`), con los filetes al 42 % y los fondos tenues al 7-8 %.
3. **Semáforo con ondas.** El indicador de estado emite ondas concéntricas desde el punto central. Especificación completa en `ADDENDUM-01-onda-estado.md`.

El tema oscuro y toda la tipografía, el espaciado y la redacción siguen igual que en la primera entrega.

## Fidelity
- `Mockup ProtexiumAI.dc.html` — **alta fidelidad**. Colores, tipografía, espaciado y estados son definitivos. Reprodúcelo con precisión.
- `Wireframes ProtexiumAI.dc.html` — **baja fidelidad**. Sirve para entender la estructura, el inventario de pantallas y las alternativas descartadas. No tomes de aquí ningún color ni tipografía.

## Principio de diseño no negociable
`src/executor.py` define tres niveles por herramienta: `lectura`, `accion`, `mutante`.
- `lectura` se ejecuta sola, sin fricción. La UI lo dice explícitamente ("solo lectura, no cambio nada").
- `accion` y `mutante` **nunca** se ejecutan solas: exigen un clic explícito del usuario. Mientras hay una propuesta pendiente, la entrada de texto queda visiblemente bloqueada y el turno no avanza.
Cualquier cambio visual debe conservar esta distinción como concepto legible a simple vista. Es el núcleo del proyecto y se defiende ante un tribunal académico: en 10 segundos de demo debe quedar claro que la aplicación es para gente sin conocimientos técnicos y que nada ocurre sin autorización.

## Decisiones de redacción (aplícalas tal cual)
- La jerga sale de la superficie. La etiqueta de nivel se muestra como **"Cambia un ajuste"** (`accion`/`mutante` que altera configuración), **"Borra datos"** (`remove_all_threats`) o **"Analiza el equipo"** (`start_quick_scan`). Las palabras `accion` / `mutante` y el `tool_id` solo aparecen dentro del detalle técnico plegado.
- Botones: **"Sí, adelante"** / **"No, déjalo"** en lugar de Confirmar / Cancelar.
- El `st.json` de parámetros desaparece de la vista principal. Se sustituye por dos filas fijas: **Qué consigues** y **Se deshace** (sí/no). El JSON, el `tool_id`, el nivel real y el comando de PowerShell viven en el bloque plegable "Ver el detalle técnico".
- Los perfiles del firewall se nombran en llano: `Domain` → "Red del trabajo", `Private` → "Red de casa", `Public` → "Redes públicas".

## Design Tokens

Paleta: Windows 11 / Fluent y colores de estado de Seguridad de Windows, con el tema claro atenuado a una escala de grises cálidos (menos contraste que el blanco de Fluent) y el azul de acento algo más saturado. El tema claro se ha rebajado sobre los valores de fábrica de Fluent (`#F3F3F3` / `#FBFBFB`) hacia una escala de grises más templada y de menor contraste, manteniéndolo claro; el acento se ha saturado un paso. Tipografía: Cormorant Garamond + Lora (Google Fonts).

### Colores — tema claro
| Rol | Valor | Uso |
| --- | --- | --- |
| Lienzo tras la ventana | `#BEBEBC` | fondo del escritorio en el prototipo |
| Fondo de página | `#DADAD8` | área principal de la ventana |
| Panel | `#D2D2D0` | barra lateral, barra de entrada, tarjetas de panel (más oscuro que el fondo, no más claro) |
| Superficie | `#E0E0DE` | capas sobre el panel (tarjeta del detalle técnico) |
| Texto primario | `#292928` | |
| Texto secundario | `#6B6B69` | micro-rótulos, metadatos |
| Filete fino | `rgba(0,0,0,.085)` | separadores y bordes de tarjeta |
| Filete marcado | `rgba(0,0,0,.16)` | borde de la ventana, botón secundario, burbuja del usuario |
| Acento | `#0A6DD6` | filete de la tarjeta de permiso, rótulo "Protexium", flechas, botón primario |
| Acento 42 % | `rgba(10,109,214,.42)` | filetes internos de la tarjeta de permiso, hilo del rail |
| Acento 7 % | `rgba(10,109,214,.07)` | fondo tenue de la tarjeta de permiso y de la pestaña activa |
| Estado correcto | `#0F7B0F` | |
| Estado atención | `#9D5D00` | |
| Estado crítico | `#C42B1C` | |
| Sombra | `0 8px 24px rgba(0,0,0,.10)` | |

### Colores — tema oscuro
| Rol | Valor |
| --- | --- |
| Fondo de página | `#202020` |
| Panel / tarjeta | `#272727` |
| Superficie | `#2C2C2C` |
| Texto primario | `#FFFFFF` |
| Texto secundario | `#A0A0A0` |
| Filete fino | `rgba(255,255,255,.0698)` |
| Filete marcado | `rgba(255,255,255,.18)` |
| Acento | `#5CC8FF` |
| Acento 42 % | `rgba(92,200,255,.42)` |
| Acento 8 % | `rgba(92,200,255,.08)` |
| Estado correcto | `#6CCB5F` |
| Estado atención | `#FCE100` |
| Estado crítico | `#FF99A4` |
| Sombra | `0 12px 40px rgba(0,0,0,.55)` |

En el prototipo los temas son dos bloques de variables CSS (`.pxa` y `.pxa[data-p="dark"]`); en Streamlit corresponden a `base = "light"` / `"dark"` en `.streamlit/config.toml` más las mismas variables en el CSS inyectado.

### Tipografía
| Elemento | Fuente | Tamaño / interlineado | Peso | Otros |
| --- | --- | --- | --- | --- |
| Display (saludo, titulares de tarjeta) | Cormorant Garamond | 46 px / 1.08 · 29 px / 1.15-1.2 | 400 | `letter-spacing:-.01em` |
| Título de sección (marca, estado, fecha) | Cormorant Garamond | 25 px · 20 px / 1.1 | 400-600 | |
| Texto corrido (respuestas del asistente) | Lora | 15 px / 1.75 | 400 | `text-align:justify`, `text-wrap:pretty` |
| Texto de interfaz | Lora | 13-14.5 px / 1.45-1.7 | 400 | |
| Micro-rótulo (versalitas) | Lora | 9.5-11 px | 400 | `letter-spacing:.12-.19em`, `text-transform:uppercase` |
| Metadato / nota | Lora | 10.5-11.5 px / 1.45 | 400 | color secundario; las notas de sistema en cursiva |
| Cifras | ambas | — | — | `font-variant-numeric:tabular-nums` en horas, fechas, `tool_id` y comandos |

Nunca negrita: el énfasis es la cursiva, el color o el tamaño. No introducir una sans-serif.

### Espaciado, radios y trazos
- Escala de espaciado (densidad 1.15×): `4.6 · 9.2 · 13.8 · 18.4 · 27.6 · 36.8` px. Padding de la barra lateral y del panel principal: `27.6px` / `36.8px`.
- Radios: `8px` la ventana, `4px` tarjetas y controles, `2px` la etiqueta de nivel, `50%` los anillos de estado.
- Todos los bordes son de `1px`. No hay rellenos de color sólido: el color se aplica como trazo, filete y subrayado. Los botones son de contorno, nunca azul relleno.
- Los separadores son `<div>` de 1 px de alto con el filete fino, no `border-bottom` sobre texto.

## Screens / Views

Marco del prototipo: 1180 × 764 px. Barra lateral fija de 272 px + área principal flexible. La barra superior de pestañas del prototipo (Inicio · Conversación · Permiso · Resultado · Sin conexión) **es un conmutador de demo**, no parte del producto: en la app real la pantalla la determina el estado del turno.

### 1. Barra lateral (presente en todas las pantallas)
- Ancho 272 px, fondo panel, borde derecho filete fino, y un hilo vertical de 1 px en el borde izquierdo con degradado `transparent → acento 42% (22%–78%) → transparent`.
- **Marca**: círculo de 30 px con borde de acento y, dentro, un cuadrado de 11 px rotado 45°; al lado "Protexium" en Cormorant 25 px con "AI" en color de acento. Debajo, "Asistente de seguridad para Windows 11" (11.5 px, secundario, máx. 190 px).
- **Estado del equipo**: micro-rótulo a la izquierda y hora (`10:04`, cifras tabulares) a la derecha. Semáforo de 44 px con **animación de ondas** que salen del punto central — composición, keyframes y notas en `ADDENDUM-01-onda-estado.md`, que es la referencia de esta pieza. En resumen: tres anillos de 1 px animados (ciclo de 3 s, desfases 0/1/2 s), un anillo exterior estático al 32 % de opacidad, anillo interior de 26 px y punto central de 7 px, todos en el color de estado (verde / ámbar / rojo). A la derecha, titular Cormorant 20 px (`Equipo protegido` / `Requiere atención`) y nota de 11 px. Sustituye al `st.markdown(f"### {color} {mensaje}")` actual y se alimenta de `_calcular_semaforo()`.
- **Tabla de comprobaciones**: filas de 6 px de padding separadas por filetes, etiqueta a la izquierda y valor a la derecha en secundario — "Vigilancia en tiempo real: activa" (`RealTimeProtectionEnabled`), "Firmas de virus: al día" (`AntivirusSignatureLastUpdated`), "Firewall: 3 de 3 redes" (`Get-NetFirewallProfile`, en color de estado).
- **Botón "Volver a comprobar"**: contorno filete marcado, 11.5 px, `letter-spacing:.06em`, radio 4. Hover: borde y texto en acento. Equivale al botón "🔄 Actualizar estado".
- **Dónde se procesa**: dos tarjetas de opción apiladas. La activa lleva borde de acento y fondo acento 7 %, punto relleno de 5 px, título 13 px y consecuencia en 10.5 px secundario ("En la nube · Groq / Tus preguntas salen del equipo"; "En este equipo · Ollama / Nada sale de tu ordenador"). Sustituye al `st.radio` + `st.caption` de `NOTA_PRIVACIDAD`.
- **Apariencia** (al fondo): micro-rótulo y un conmutador Claro/Oscuro de dos botones dentro de un contorno de 4 px; el activo lleva fondo acento 7 % y texto de acento. Debajo, en 10.5 px secundario: "Nunca cambio un ajuste de tu equipo sin tu permiso."

### 2. Cabecera del área principal
Padding `18.4px 36.8px`, filete inferior. Izquierda: micro-rótulo "Sesión" y la fecha en Cormorant 20 px con cifras tabulares (`30 · VIII · 2026`). Derecha: el conmutador de demo (no llevarlo a producción).

### 3. Inicio / estado vacío
Centrado vertical y horizontal, padding `36.8px 92px`, `gap:18.4px`.
- Filete de 56 × 1 px en acento 42 %, saludo "Buenas tardes" en Cormorant 46 px peso 400, párrafo de 14.5 px / 1.7 en secundario (máx. 430 px): "Pregúntame por tu equipo con tus propias palabras. Yo lo reviso y te lo explico sin tecnicismos." Otro filete de 56 px.
- Micro-rótulo "Para empezar" y tres sugerencias en columna (máx. 520 px): contorno filete fino, padding `13.8px 18.4px`, texto 14.5 px a la izquierda y flecha `→` en acento a la derecha. Hover: borde de acento y fondo acento 7 %. Textos: "¿Cómo está mi PC?", "Me ha salido una alerta rara", "¿Tengo el firewall encendido?". Al pulsar, envían ese texto como mensaje del usuario.

### 4. Conversación
Padding `27.6px 36.8px`, `gap:27.6px`, con scroll.
- **Mensaje del usuario**: alineado a la derecha, máx. 62 %, micro-rótulo "Tú" encima y burbuja con contorno filete marcado, radio 4, padding `11px 18.4px`, 14.5 px. Sin relleno de color.
- **Respuesta del asistente**: máx. 76 %, sin burbuja. Micro-rótulo "Protexium" en color de acento y párrafos Lora 15 px / 1.75 justificados. Un solo enlace discreto debajo: "Qué he consultado · 2 lecturas" (10.5 px versalitas, subrayado con filete marcado) que despliega las lecturas ejecutadas.
- **Estado pensando**: tres puntos de 4 px en acento con `@keyframes` de opacidad `.25 → .9` (1.4 s, `ease-in-out`, desfases 0 / .2 / .4 s) y, al lado, en cursiva 13 px secundario, lo que está haciendo: "Reviso las amenazas detectadas · solo lectura, no cambio nada". Sustituye a `st.spinner("ProtexiumAI está pensando...")` y debe nombrar la herramienta en curso.

### 5. Permiso pendiente (pantalla clave)
Tarjeta de máx. 660 px, borde de 1 px en acento, radio 4, fondo acento 7 %, sin sombra.
- **Cabecera** (`13.8px 27.6px`, filete inferior en acento 42 %): a la izquierda micro-rótulo "Necesito tu permiso" en acento; a la derecha la etiqueta de nivel en versalitas 9.5 px, contorno acento 42 %, radio 2, padding `3px 11px`, `white-space:nowrap`.
- **Cuerpo** (`22px 27.6px`, `gap:18.4px`): titular Cormorant 29 px peso 400 con la acción en llano y en primera persona — "Voy a encender el firewall cuando te conectes a redes públicas" (viene de `descripcion` en la propuesta).
- **Dos filas de definición** separadas por filetes: columna izquierda de 120 px con micro-rótulo, derecha con texto de 13.5 px / 1.6. "Qué consigues": consecuencia en lenguaje llano. "Se deshace": "Sí. Pídeme lo contrario y lo apago." / "No." Este par sustituye al `st.json`.
- **Enlace "Ver el detalle técnico"** (11 px versalitas, subrayado). Al abrirse muestra una tarjeta interior con contorno filete fino, fondo de página y cuatro filas etiqueta/valor de 12 px: Herramienta (`set_firewall_profile`), Nivel (`mutante · requiere administrador`), Comando (`Set-NetFirewallProfile -Profile Public -Enabled True`, cifras tabulares) y Auditoría ("se registra antes de ejecutarse"). El comando debe salir de `spec.plantilla.format(**params)`, no escribirse a mano.
- **Botones**: "Sí, adelante" en Cormorant 600 15 px con contorno de acento, padding `11px 27.6px`; hover fondo acento 42 % y texto primario. "No, déjalo" con contorno filete marcado, Lora 13.5 px, padding `11px 22px`; hover borde de texto primario. A la derecha del todo, en cursiva 11.5 px secundario: "Nada ocurre hasta que pulses."
- **Aviso de administrador** (cuando `spec.requiere_admin and not executor._es_administrador()`): tarjeta con contorno discontinuo dentro de la misma tarjeta, texto "Esta orden necesita permisos de administrador. Cierra y vuelve a abrir ProtexiumAI como administrador para poder autorizarla." y el botón "Sí, adelante" deshabilitado (opacidad 45 %).
- Mientras esta tarjeta está en pantalla, la barra de entrada muestra "Responde arriba para seguir escribiendo" y la acción de la derecha dice "En espera"; el semáforo de la barra lateral pasa a ámbar.

### 6. Resultado del turno
- Primero la respuesta: micro-rótulo "Protexium", titular Cormorant 29 px con el desenlace en una frase ("Ya está: el firewall vuelve a estar encendido en las tres redes.") y un párrafo justificado de 15 px en secundario con el matiz (lo que quedó sin hacer y por qué).
- Debajo, **recibo** de máx. 720 px con contorno filete fino y radio 4. Cabecera con "Qué he hecho" a la izquierda y "3 pasos · 10:03" a la derecha. Una fila por herramienta (`padding:13.8px 18.4px`, filete inferior): marca de 14 px en acento (`✓` ejecutada, `—` no ejecutada, `!` error), título en llano de 14.5 px, metadato de 11 px con `tool_id · nivel`, y a la derecha en versalitas 10.5 px **quién lo autorizó**: "sin permiso" (lectura), "lo autorizaste tú", "lo rechazaste tú". Última fila: enlace "Ver el registro de auditoría" (`src/audit.py`).
- Sustituye a `_formatear_resultado()`, invirtiendo el orden actual: primero la prosa, después el recibo.

### 7. Sin conexión
Tarjeta centrada de máx. 560 px, contorno filete marcado, fondo panel, padding `27.6px`.
- Micro-rótulo "No he podido conectar", titular Cormorant 29 px ("No consigo hablar con Groq ahora mismo"), filete, y el párrafo que separa las dos cosas: "Tu equipo sigue igual de protegido. Esto solo afecta a nuestra conversación, no a tu seguridad."
- Botones "Reintentar" (contorno de acento) y "Usar el modo local" (contorno filete marcado), más enlace "Detalle técnico del error".
- Variantes por excepción, con el mismo molde (ver `_formatear_error()`): `AuthenticationError` → "Falta la clave de acceso a Groq" + cómo añadir `GROQ_API_KEY` al `.env`; `APIConnectionError` con Ollama → comprobar `ollama serve` y `ollama pull llama3.2:3b`; `APIError` genérico. Nunca como texto en negrita dentro de una burbuja de chat.

### 8. Barra de entrada (pie, presente siempre)
Padding `18.4px 36.8px 22px`, filete superior. Caja con contorno filete fino, fondo panel, radio 4, padding `13.8px 18.4px`: a la izquierda el placeholder ("Escribe tu pregunta…"), a la derecha en versalitas 10.5 px la acción en acento ("Enviar" / "En espera"). Debajo, en 10.5 px secundario, la línea que resume el contrato de seguridad: "Lectura sin permiso · acciones y cambios, solo con tu clic · todo queda registrado".

## Interactions & Behavior
- **Turno normal**: el usuario envía → aparece el indicador de puntos con la herramienta en curso → llegan las lecturas → respuesta + recibo. La entrada se deshabilita durante el turno (ya lo hace `st.chat_input(disabled=...)`), pero ahora además lo dice.
- **Turno con propuesta**: el hilo trabajador publica la propuesta y espera en `evento_decision`; la UI muestra la tarjeta de permiso y bloquea la entrada. "Sí, adelante" → `decision = True`; "No, déjalo" → `decision = False`; en ambos casos `evento_decision.set()` y `st.rerun()`. Sin cambios en `_confirmar()` / `EstadoTurno`.
- **Tras una mutación con éxito** se recalcula el semáforo (ya ocurre en `_gestionar_turno_en_curso`); el anillo de estado cambia de color.
- **Detalle técnico**: plegado por defecto en la propuesta y en el recibo. En Streamlit, `st.expander` con el estilo del CSS inyectado.
- **Hover**: tarjetas y sugerencias pasan el borde a acento y el fondo a acento 7 %; los botones de contorno oscurecen o rellenan al 42 % de acento. Transiciones cortas (120–160 ms, `ease-out`); solo se animan de forma continua dos cosas: las ondas del semáforo de estado y los tres puntos del estado pensando.
- **Foco de teclado**: contorno de 2 px en color de acento con `outline-offset:2px`. Los dos botones de la propuesta deben ser alcanzables con Tab; no debe haber ningún atajo que confirme sin clic o Enter explícito sobre el botón.
- **Temas**: claro / oscuro conmutables desde la barra lateral; conviene recordar la elección (`st.session_state` + `.streamlit/config.toml` como valor inicial).

## State Management
Nada nuevo respecto a lo que ya existe en `app/streamlit_app.py`; solo se añade lo de apariencia:
- `historial_ui`, `agente`, `proveedor_actual`, `hilo`, `contenedor_estado`, `estado_defender`, `estado_firewall`, `semaforo` — ya presentes.
- `EstadoTurno`: `evento_decision`, `propuesta` (`tool_id`, `descripcion`, `params`, `nivel`), `decision`, `resultado`, `error`, `terminado` — ya presentes.
- Nuevos: `tema` (`"light"` | `"dark"`) y `detalle_abierto` por propuesta.
- Datos que la UI necesita y hoy no muestra: hora de la confirmación de cada herramienta, y el `comando` ya formateado del resultado de `executor.execute` para el detalle técnico.

## Assets
Ninguna imagen. La marca es un círculo con un cuadrado rotado 45° dibujado con dos `div` (o un SVG equivalente); no se usa el emoji 🛡️. Iconografía: Lucide (`lucide.dev`) si hace falta más allá de las marcas `✓` / `—` / `!`. Fuentes desde Google Fonts: Cormorant Garamond (400, 600) y Lora (400, 600).

## Pantallas del paquete

Diez estados, todos en `Mockup ProtexiumAI.dc.html`.

> **La fila de pestañas de la cabecera del mockup NO va al producto.** Es un conmutador de demo para poder
> ver los diez estados sin provocarlos. En la app, la pantalla la determina el estado del turno: hay una
> propuesta pendiente → tarjeta de permiso; hay una acción autorizada en marcha → pantalla "ejecutando";
> el turno terminó → resultado. Solo tres pantallas necesitan navegación explícita, y su acceso ya está
> dentro de la interfaz: **Estado en detalle** desde el botón "Ver el detalle" de la barra lateral,
> **Auditoría** desde el enlace al pie del recibo del turno, y **Catálogo** desde "Ver todo lo que puedo
> mirar" en la bienvenida. No añadas una barra de navegación por pantallas.

| # | Pantalla | Dónde está descrita |
| --- | --- | --- |
| 1 | Inicio / bienvenida | README §3 + ADDENDUM-02 §12 (conversación nueva) |
| 2 | Conversación | README §4 + ADDENDUM-02 §4 (indicador), §11 (proveedor por turno) |
| 3 | Permiso pendiente | README §5 + ADDENDUM-02 §7 (parámetros), §8 (cola), §9 (administrador) |
| 4 | Permiso irreversible | ADDENDUM-02 §6 |
| 5 | Ejecutando | ADDENDUM-02 §4 |
| 6 | Resultado del turno | README §6 + ADDENDUM-02 §2 (nombres en llano), §13 (resultado sin datos) |
| 7 | Estado del equipo en detalle | ADDENDUM-02 §9, §10, §14 |
| 8 | Registro de auditoría | ADDENDUM-02 §3, §11 |
| 9 | Catálogo de preguntas | ADDENDUM-02 (pantalla A3; agrupada por los mismos cinco bloques del §7 de estado) |
| 10 | Fallos del sistema | ADDENDUM-02 §5 |

## Mapa pantalla → archivos del repositorio

| Pantalla | Archivos |
| --- | --- |
| 1 Inicio | `app/streamlit_app.py` |
| 2 Conversación | `app/streamlit_app.py`, `src/agent.py` |
| 3 y 4 Permiso | `app/streamlit_app.py`, `src/executor.py` (WHITELIST, niveles, `requiere_admin`, plantillas) |
| 5 Ejecutando | `src/agent.py`, `src/executor.py` (tiempos máximos por herramienta) |
| 6 Resultado | `app/streamlit_app.py` (`_formatear_resultado`), `src/audit.py` |
| 7 Estado en detalle | `src/executor.py` (las 17 lecturas), `app/streamlit_app.py` (`_calcular_semaforo`) |
| 8 Auditoría | `src/audit.py` (entradas y `motivo_rechazo`) |
| 9 Catálogo | `src/tools_schema.py` (descripciones de las 25) |
| 10 Fallos | `src/executor.py` (errores de ejecución), `app/streamlit_app.py` (`_formatear_error`) |
| Barra lateral · sesión | `src/executor.py` (`get_account_info`, `_es_administrador`) |
| Tema claro / oscuro | `.streamlit/config.toml`, `app/estilos.css` — valores en ADDENDUM-02 §1 |

## Files
- `Mockup ProtexiumAI.dc.html` — mockup de alta fidelidad, cinco pantallas conmutables y los dos temas. Fuente de verdad de colores, tipografía y espaciado.
- `ADDENDUM-01-onda-estado.md` — animación de ondas del semáforo de estado. Es parte del diseño, no opcional.
- `ADDENDUM-02-25-herramientas.md` — ampliación a 25 herramientas: pantallas nuevas, nombres en llano de las 25, motivos de rechazo en llano, molde de errores del sistema, operaciones irreversibles y tokens de `.streamlit/config.toml`.
- `Wireframes ProtexiumAI.dc.html` — dos rondas de wireframes: turno 1 con cuatro estructuras y cuatro tratamientos de la confirmación (alternativas descartadas), turno 2 con las nueve pantallas de la dirección elegida.
- `github.md` — asociación con el repositorio de origen y mapa de pantalla → archivos del repo.
- Los archivos `.dc.html` se abren directamente en el navegador. Requieren la carpeta `_ds/` del sistema de diseño solo para las fuentes y algunos tokens; los valores que importan están todos escritos en este README.
