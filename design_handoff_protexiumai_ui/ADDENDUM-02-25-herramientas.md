# Addendum 02 — Ampliación a 25 herramientas

Complementa al `README.md` y al `ADDENDUM-01-onda-estado.md`. No sustituye nada: la paleta, la tipografía, la escala de espaciado, los radios, los trazos de 1 px, los botones de contorno y toda la redacción ya fijada siguen vigentes. Aquí solo está lo nuevo.

Fuente visual: `Mockup ProtexiumAI.dc.html`, ahora con diez pantallas en el conmutador de demo (Inicio, Conversación, Permiso, Irreversible, Ejecutando, Resultado, Estado, Auditoría, Catálogo, Fallos).

---

## 1. Tokens que se añaden

Solo tres, derivados del color de estado crítico que ya existía:

| Token | Claro | Oscuro | Uso |
| --- | --- | --- | --- |
| `--p-bad` (ya existía) | `#C42B1C` | `#FF99A4` | contorno y titulares de las operaciones irreversibles |
| `--p-bad-soft` | `rgba(196,43,28,.42)` | `rgba(255,153,164,.42)` | filetes internos de esa tarjeta, subrayados |
| `--p-bad-tint` | `rgba(196,43,28,.06)` | `rgba(255,153,164,.07)` | fondo tenue de esa tarjeta |

Nada más. No se introduce ningún color nuevo ni ninguna fuente.

### Valores exactos para `.streamlit/config.toml`

El archivo conserva la paleta de la primera entrega. Debe quedar así:

```toml
[theme]
base = "light"
primaryColor = "#0A6DD6"
backgroundColor = "#DADAD8"
secondaryBackgroundColor = "#D2D2D0"
textColor = "#292928"
font = "serif"
```

`config.toml` solo puede declarar un tema, y se lee al arrancar: es el **tema de partida** y el que viste el cromado propio de Streamlit (barra superior, menú, widgets nativos). El conmutador Claro/Oscuro de la barra lateral cambia las variables CSS del HTML propio, que es el 95 % de la superficie. Para que el cromado nativo no se quede claro sobre una interfaz oscura, aplica en el CSS inyectado los mismos tokens a los contenedores raíz de Streamlit (`[data-testid="stAppViewContainer"]`, `[data-testid="stHeader"]`, `[data-testid="stSidebar"]`, `.stChatInput`) leyendo `var(--p-bg)` / `var(--p-panel)` / `var(--p-ink)`, en lugar de dejarlos con el color del tema nativo.

**Tema del sistema: no.** Dos opciones, Claro y Oscuro, y se recuerda la elección en `st.session_state`. Streamlit no expone `prefers-color-scheme` al servidor sin un componente extra, así que "Sistema" sería una promesa que la app no puede cumplir de forma fiable. El wireframe `2g` queda descartado en este punto.

---

## 2. Nombres en llano de las 25 herramientas

En primera persona, en la voz del asistente. Se usan en el recibo del turno, en el desplegable "Qué he consultado" y en el registro de auditoría. El `tool_id` solo aparece en el detalle técnico.

### Cuando la operación se ha hecho

| tool_id | Nombre en llano |
| --- | --- |
| get_defender_status | He mirado el estado de Defender |
| get_detected_threats | He mirado si hay amenazas detectadas |
| get_firewall_status | He mirado el estado del firewall |
| get_active_network_profile | He mirado a qué red estás conectado |
| get_account_info | He mirado con qué cuenta has entrado |
| get_allowed_threats | He mirado qué amenazas permitiste tú |
| get_defender_preferences | He mirado los ajustes de Defender |
| get_exploit_protection_status | He mirado la protección contra exploits |
| get_allowed_firewall_rules | He mirado qué aplicaciones pueden entrar |
| get_core_isolation_status | He mirado el aislamiento del núcleo |
| get_storage_status | He mirado el espacio libre de los discos |
| get_battery_status | He mirado el estado de la batería |
| get_time_service_status | He mirado si la hora del equipo se sincroniza |
| get_defender_exclusions | He mirado qué carpetas quedan fuera del análisis |
| get_secure_boot_status | He mirado si el arranque seguro está activo |
| get_tpm_status | He mirado el chip de seguridad del equipo |
| get_bitlocker_status | He mirado si tus discos están cifrados |
| start_quick_scan | He analizado el equipo por encima |
| start_full_scan | He analizado el equipo entero |
| start_custom_scan | He analizado la carpeta {carpeta} |
| update_signatures | He actualizado las definiciones de virus |
| set_firewall_profile | He {encendido/apagado} el firewall en {red} |
| set_block_all_incoming | He {bloqueado/restaurado} las conexiones entrantes en {red} |
| remove_all_threats | He eliminado las amenazas detectadas |
| restore_firewall_defaults | He restaurado las reglas del firewall de fábrica |

### Cuando no se ha hecho

Misma frase en negativo, sin culpabilizar: "No he analizado el equipo", "No he podido mirar el cifrado del disco", "No he quitado ninguna amenaza".

### Cuando está en curso (gerundio)

"Estoy mirando el estado del firewall", "Estoy analizando el equipo entero". Ver la sección 4.

### Traducción a llano de los valores de parámetro

| Valor técnico | En llano |
| --- | --- |
| Domain | Red del trabajo |
| Private | Red de casa |
| Public | Redes públicas |
| Downloads | Tu carpeta de Descargas |
| Desktop | Tu Escritorio |
| Documents | Tu carpeta de Documentos |
| activar = True | encender |
| activar = False | apagar |
| restaurar = True | volver a dejarlo como estaba |

---

## 3. Traducción de los siete motivos de rechazo

Se usan en el registro de auditoría (columna de resultado) y en el recibo del turno. Ninguno culpa al usuario.

| motivo_rechazo | En llano | Cuándo |
| --- | --- | --- |
| usuario_rechazo | Sin hacer · me dijiste que no | El usuario pulsó "No, déjalo" |
| requiere_admin | Sin hacer · hace falta abrir como administrador | Sesión sin elevar |
| tool_id_desconocido | Sin hacer · esa operación no está en mi lista | El modelo pidió algo fuera de la whitelist |
| parametro_no_declarado | Sin hacer · me pedía un dato que no puedo aceptar | Parámetro no declarado en el esquema |
| parametro_faltante | Sin hacer · faltaba un dato para poder ejecutarlo | Falta un parámetro obligatorio |
| valor_fuera_de_enum | Sin hacer · el valor pedido no es uno de los permitidos | Fuera del enum |
| argumentos_invalidos | Sin hacer · la petición no llegó en un formato que entienda | JSON inválido |

Los cuatro últimos son la whitelist funcionando, no un fallo: en el detalle técnico se muestran con el `tool_id` y el parámetro concreto, y en la defensa se pueden enseñar como prueba de que nada fuera del catálogo llega a ejecutarse.

---

## 4. Plantillas del indicador de estado

Tres textos distintos, uno por situación. Siempre en cursiva, 13 px, color secundario, junto a los tres puntos.

| Situación | Plantilla | Ejemplo |
| --- | --- | --- |
| Lectura en curso | `Estoy {gerundio} · solo miro, no cambio nada` | *Estoy mirando las amenazas detectadas · solo miro, no cambio nada* |
| Esperando autorización | No hay indicador: la tarjeta de permiso ocupa su lugar y la barra de entrada dice "Responde arriba para seguir escribiendo" | — |
| Acción autorizada en curso | Bloque propio, ver abajo | — |

El texto fijo *"solo lectura, no cambio nada"* deja de usarse cuando lo que corre es una acción.

### Bloque "ejecutando"

No es una línea, es una tarjeta con contorno de filete marcado, fondo de panel, padding `22px 27.6px`. Reutiliza los tres puntos de "pensando"; **no lleva barra de progreso** porque el sistema no da porcentaje real. Contiene, en orden:

1. Fila superior: los tres puntos, micro-rótulo "Trabajando en tu equipo" en color de acento, y a la derecha el tiempo transcurrido en cifras tabulares (`04:12 transcurridos`).
2. Titular Cormorant 29 px con el gerundio: "Estoy analizando el equipo entero".
3. Filete.
4. Expectativa realista, 13.5 px: "Un análisis completo puede tardar hasta una hora. Puedes seguir usando el ordenador; te aviso al terminar." Duraciones por herramienta: rápido 10 min, personalizado 15 min, completo 1 h, definiciones ~2 min.
5. Recordatorio de la autorización, 12 px secundario: "Lo autorizaste tú a las 10:07. Puedo pararlo cuando quieras."
6. Botón de contorno "Para el análisis" y enlace "Ver el detalle técnico".

### Desenlace por tiempo agotado

No es un error y no usa el color crítico. Tarjeta de contorno fino con titular "El análisis sigue en marcha por su cuenta" y el texto: *"He dejado de esperar al llegar a una hora, pero Windows lo sigue haciendo en segundo plano. No es un fallo tuyo ni del equipo: pregúntame dentro de un rato y miro cómo ha quedado."* Dos botones: "Mira cómo va" (acento) y "Déjalo por ahora".

---

## 5. Molde de los errores del sistema

Misma estructura que la tarjeta "Sin conexión", que se queda como está para los fallos del proveedor de IA. El molde común, en este orden:

1. Micro-rótulo de categoría: "No he podido terminar".
2. Titular Cormorant 29 px: qué ha pasado, en llano y sin jerga.
3. Filete.
4. **Primero la tranquilidad**: "Tu equipo sigue igual de protegido y no he cambiado nada."
5. Después, qué se puede hacer: dos botones, el primero de acento.
6. Enlace "Ver el detalle técnico" con la excepción real, el `tool_id` y la salida de PowerShell.

Los cinco casos, con su titular y su segunda línea:

| Caso | Titular | Segunda línea |
| --- | --- | --- |
| Tiempo agotado al ejecutar | El equipo ha tardado más de lo que puedo esperar | Solo se ha quedado a medias la consulta que te iba a responder. |
| PowerShell no encontrado | No encuentro PowerShell en el equipo | Sin PowerShell no puedo consultar nada; suele arreglarse reiniciando Windows. |
| Salida ilegible | No he entendido lo que me ha devuelto el equipo | La respuesta llegó en un formato que no sé leer; puedo intentarlo otra vez. |
| Requiere elevación | Esto necesita abrir la app como administrador | No he cambiado nada. Nunca te pediré la contraseña. |
| El agente no converge | Me he liado dando vueltas y no he llegado a nada | Prueba a preguntármelo de otra forma, más concreta. |
| Error de PowerShell | Windows me ha dado un error al ejecutar la orden | El cambio no se ha aplicado; te dejo el error exacto en el detalle. |

---

## 6. Operaciones irreversibles

Afecta a `remove_all_threats` y `restore_firewall_defaults`.

**No se añade un segundo clic de confirmación.** Un segundo clic enseña a pulsar dos veces sin leer y desgasta el gesto que sostiene todo el proyecto: si el usuario aprende que confirmar es un trámite doble, la confirmación de las ocho operaciones pierde peso. Lo que se hace es dar a la tarjeta un aspecto inequívocamente distinto y **mostrar el alcance antes de actuar**.

Cambios respecto a la tarjeta de permiso normal:
- Contorno, filetes internos, micro-rótulo, titular de la fila "Se deshace" y botón primario en `--p-bad`; fondo en `--p-bad-tint`. Sigue siendo tarjeta de contorno: **ningún relleno sólido**.
- Micro-rótulo ampliado: "Necesito tu permiso · esto no se deshace".
- **Segunda etiqueta** junto a la de nivel: "Sin vuelta atrás", contorno de `--p-bad`. La etiqueta de nivel no cambia ("Borra datos" / "Cambia un ajuste"): el distintivo es aditivo, así que no hay que inventar un cuarto nivel ni renombrar los tres existentes.
- La fila "Se deshace" dice "No. Una vez borrados no puedo recuperarlos." en `--p-bad`.
- Enlace nuevo junto al detalle técnico: "Ver qué se va a borrar · 2", que lista las amenazas o las reglas afectadas. Es la alternativa al segundo clic: en lugar de repetir la pregunta, se enseña el contenido.
- Nota de una línea con contorno discontinuo: "Esto no se puede deshacer. Si prefieres verlas antes, pídemelo y te las enseño una a una sin tocar nada."
- El botón nombra lo que hace: "Sí, bórralas" / "Sí, restaura el firewall", no "Sí, adelante".

Para `restore_firewall_defaults` el alcance es "Todas las reglas del firewall, incluidas las 6 que creaste tú" y el enlace es "Ver qué reglas se pierden · 6".

---

## 7. Propuestas con parámetros

La tarjeta de permiso gana una **primera fila de definición, "Sobre qué"**, antes de "Qué consigues". Muestra el alcance traducido a llano, nunca el valor técnico:

- `start_custom_scan` → "Tu carpeta de Descargas · C:\Users\juan\Downloads"
- `set_firewall_profile` → "Solo el perfil de redes públicas. Tu red de casa y la del trabajo se quedan como están."
- `set_block_all_incoming` → "Redes públicas · se bloquean también las apps que hoy tienen permiso"
- `remove_all_threats` → "2 archivos en cuarentena · Trojan:Win32/Wacatac y PUA:Win32/Presenoker"

Cuando la herramienta no tiene parámetros (análisis rápido, análisis completo, definiciones), la fila dice "Todo el equipo" o "Las definiciones de virus de Windows Defender"; no se omite, para que las cuatro tarjetas tengan la misma anatomía.

---

## 8. Varias autorizaciones en un turno

Dos piezas coordinadas:

1. **En la barra lateral**, bajo el estado de la sesión, una tarjeta de contorno de acento: micro-rótulo "Esperando tu decisión" y el texto "Orden 1 de 3 · las otras dos esperan su turno". Desaparece cuando la cola se vacía.
2. **En la tarjeta**, sobre el titular, un micro-rótulo "Orden 1 de 3" en versalitas.

Las órdenes se resuelven de una en una, en el orden en que el agente las propuso. Rechazar una no cancela las siguientes: cada una se presenta con su propia tarjeta. Si el usuario rechaza una de la que dependen las demás, el turno termina y el recibo lo explica.

---

## 9. Estado de administrador a nivel de sesión

`get_account_info` es de lectura y no necesita elevación, así que la app sabe desde el primer segundo si puede o no ejecutar las 12 herramientas elevadas (4 de ellas de solo lectura). Se informa **antes**, no en el momento del rechazo.

**En la barra lateral**, sección propia entre el estado del equipo y el proveedor:

> ESTA SESIÓN · Sin administrador
> Como juan, usuario estándar. 4 comprobaciones y 8 acciones no estarán disponibles.
> [Qué significa]

Si la sesión sí está elevada: "Con administrador · Puedo consultarlo y hacerlo todo." en color secundario, sin destacar — tener permisos no es un logro que anunciar.

**En la pantalla de estado en detalle**, las filas que necesitan elevación muestran "Necesito administrador" en color secundario con un subrayado punteado de 1 px, distinto del valor normal y distinto de "no aplica".

**En la tarjeta de permiso**, el aviso se queda donde estaba, ahora al pie y separado por un filete: micro-rótulo "Necesita administrador" en ámbar y el texto "Ahora mismo la sesión es de usuario estándar. Cierra ProtexiumAI y vuelve a abrirlo como administrador para poder autorizarlo. No te pediré nunca tu contraseña."

La app **nunca** eleva por su cuenta, nunca lanza un UAC y nunca procesa contraseñas. El texto lo dice explícitamente porque es un punto de la defensa.

---

## 10. Vocabulario del semáforo

Cinco estados, no tres. El color sale de los tokens de estado ya existentes.

| Estado | Titular | Nota | Color |
| --- | --- | --- | --- |
| Todo correcto | Equipo protegido | Defender y el firewall están activos | `--p-ok` |
| Algo flojo | Requiere atención | (el motivo concreto, p. ej. "El firewall está apagado en redes públicas") | `--p-warn` |
| Defender en modo pasivo | Protegido por otro antivirus | Defender está en segundo plano porque tienes {nombre} instalado | `--p-ok`, anillo con trazo discontinuo |
| Sin vigilancia | Sin protección en tiempo real | Nadie está revisando los archivos que abres | `--p-bad` |
| No se pudo comprobar | No he podido comprobarlo | La consulta no ha respondido. Vuelve a intentarlo. | `--p-mute`, sin ondas |

"Protegido por otro antivirus" **no es un fallo**: mantiene el verde y solo cambia el trazo del anillo exterior a discontinuo, para que se distinga de la protección propia. "No he podido comprobarlo" detiene la animación de ondas: sin dato no hay vigilancia que representar.

---

## 11. Proveedor por turno

Junto al micro-rótulo "Protexium" de cada respuesta, en versalitas 9.5 px en color secundario: "· respondido en la nube" o "· respondido en este equipo". Es la marca que permite demostrar en la defensa que un turno concreto se procesó sin salir del equipo. En el registro de auditoría es una columna propia ("Nube" / "Local").

## 12. Conversación nueva

Botón de contorno al pie de la barra lateral: "Empezar una conversación nueva". Vacía el historial y vuelve a la pantalla de bienvenida; el registro de auditoría **no** se borra, y el texto lo dice al pulsarlo: "Empiezo de cero. El registro de lo que he hecho se conserva."

Cambiar de proveedor también reinicia la conversación, porque el historial no viaja entre modelos. La barra lateral lo advierte antes, bajo las dos tarjetas de proveedor: "Si cambias de sitio, empiezo una conversación nueva."

## 13. Resultado sin datos

Los cuatro análisis no devuelven información al terminar. El titular lo dice sin fingir un informe — "Ya está: el análisis rápido ha terminado sin encontrar nada." — el párrafo explica por qué no hay más que enseñar, y debajo va **un solo botón de acento con el siguiente paso en llano**: "¿Ha encontrado algo?" (lanza `get_detected_threats`). Nunca una tarjeta de resultados vacía ni un "0 elementos".

---

## 14. Comportamiento responsive

Las pantallas nuevas viven en el mismo marco y siguen la misma regla: la barra lateral es la de Streamlit, se pliega con su control nativo y la interfaz no depende de que esté abierta.

- **Estado en detalle**: una columna siempre; las filas son etiqueta a la izquierda y valor a la derecha, y por debajo de ~560 px de ancho el valor pasa a una segunda línea alineada a la izquierda. Nunca dos columnas.
- **Catálogo**: rejilla de dos columnas que cae a una por debajo de ~720 px.
- **Auditoría**: por debajo de ~720 px se ocultan las columnas de autor y proveedor de la fila y pasan al detalle plegado; la hora y el nombre en llano no se ocultan nunca.
- **Tarjeta de permiso**: `max-width` de 680 px; los dos botones pasan a apilarse por debajo de ~420 px, con "Sí" siempre arriba.
- Con la barra lateral plegada, el estado del equipo se convierte en una fila fina bajo la cabecera con el anillo pequeño, el titular y el enlace "Ver el detalle".

Recordatorio de las restricciones que condicionaron estos diseños: nada de arrastrar y soltar, menús contextuales, tooltips como único canal, ni scroll infinito; los desplegables son bloques plegables de un solo nivel; la animación se reinicia en cada recarga y respeta `prefers-reduced-motion`.
