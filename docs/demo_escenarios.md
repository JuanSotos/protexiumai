# Guion de la demo — defensa del TFG

> **Antes de cada ensayo y antes de la defensa real: restaura el snapshot de VirtualBox «Demo lista».**
> Todos los escenarios de este guion se ejecutan dentro de la máquina virtual de pruebas, nunca en el
> equipo de desarrollo. Ejecutar sobre un snapshot que no sea «Demo lista» invalida el guion: los
> escenarios 2 y 3 dependen de un estado inicial concreto (sin amenazas detectadas todavía, un perfil
> del firewall desactivado).

## 0. Cómo crear el snapshot «Demo lista»

Se crea una única vez (y se recrea si el proyecto cambia de forma relevante), partiendo del snapshot
«Base limpia»:

1. Arranca la VM desde el snapshot «Base limpia».
2. Abre una terminal PowerShell **como administrador**.
3. Desactiva un perfil del firewall para dejar preparado el Escenario 3:
   ```powershell
   Set-NetFirewallProfile -Profile Private -Enabled False
   ```
4. Copia `.env.example` a `.env` en la raíz del repo dentro de la VM y rellena:
   - `LLM_PROVIDER=groq` y `GROQ_API_KEY=<tu clave>` (modo nube, el usado por defecto en la demo), o
   - `LLM_PROVIDER=ollama` si vas a demostrar el modo privado (requiere Ollama instalado en la VM con
     el modelo `llama3.2:3b` ya descargado — `ollama pull llama3.2:3b`).
5. Ancla a la barra de tareas una terminal PowerShell **elevada** (clic derecho → "Ejecutar como
   administrador" → clic derecho en el icono de la barra de tareas → "Anclar a la barra de tareas").
   Es imprescindible: `set_firewall_profile` tiene `requiere_admin=True`, y sin una terminal elevada
   Streamlit no podrá confirmar la mutación del Escenario 3.
6. Comprueba que el repo arranca correctamente desde esa terminal elevada:
   ```powershell
   python -m pytest
   streamlit run app/streamlit_app.py
   ```
   Cierra Streamlit una vez comprobado que carga sin errores.
7. En VirtualBox, toma el snapshot con el nombre exacto **«Demo lista»**.

## 1. Checklist pre-demo

Repetir siempre antes de un ensayo o de la defensa, en este orden:

- [ ] Restaurar el snapshot «Demo lista» en VirtualBox.
- [ ] Arrancar la VM y esperar a que el escritorio cargue por completo.
- [ ] **Plan B de proveedor**: en el equipo anfitrión, arrancar Ollama (`ollama serve`) y comprobar con
      `ollama list` que el modelo `llama3.2:3b` está descargado y operativo, por si falla la conexión a
      Groq durante la defensa.
- [ ] Verificar conectividad a internet dentro de la VM (abrir un navegador y cargar cualquier página).
- [ ] Abrir la terminal PowerShell elevada anclada y lanzar `streamlit run app/streamlit_app.py`.
- [ ] Hacer un turno de calentamiento con `"¿cómo está mi PC?"` para confirmar que el proveedor LLM
      responde antes de que entre el tribunal (y para que el modelo/proveedor ya esté "caliente").
- [ ] Tener a mano, en una pestaña del navegador, el enlace
      `https://www.eicar.org/download-anti-malware-testfile/` para el Escenario 2.
- [ ] Tener el vídeo de plan B (ver sección 5) localizado, probado y listo para reproducir a pantalla
      completa si algo falla en directo.

## 2. Escenario 1 · Diagnóstico

**Objetivo.** Demostrar que ProtexiumAI traduce el estado técnico del sistema a lenguaje llano sin
pedir confirmación, porque solo usa herramientas de lectura.

**Preparación previa.** Ninguna especial: el estado que deja el snapshot «Demo lista» es suficiente
(basta con no haber ejecutado ya el Escenario 3 en el mismo pase).

**Frase exacta a escribir:**
```
¿cómo está mi PC?
```

**Comportamiento esperado.** El agente llama automáticamente a `get_defender_status` y a
`get_firewall_status` (ambas de nivel "lectura", sin badge de confirmación ni botones — se ejecutan
directamente). La respuesta debe incluir, en lenguaje llano:
- Si la protección en tiempo real y el antivirus están activos.
- La fecha de la última actualización de firmas.
- La fecha del último análisis rápido/completo.
- El estado de los perfiles del firewall.

En la barra lateral de Streamlit, el semáforo debe mostrarse en 🟢 (verde) — Defender y firewall
activos y protegiendo el equipo — salvo que ya se haya ejecutado el Escenario 3 antes en el mismo pase,
en cuyo caso puede seguir en 🟡 hasta reiniciar desde el snapshot.

**Qué demuestra al tribunal.** Que el agente orquesta varias herramientas de la WHITELIST en un solo
turno sin fricción para el usuario, que traduce datos técnicos de PowerShell a una explicación
accesible para un usuario doméstico, y que las operaciones de solo lectura no requieren ningún gesto de
confirmación (a diferencia de los Escenarios 2 y 3).

## 3. Escenario 2 · Amenaza real segura (EICAR)

**Objetivo.** Demostrar que el agente reacciona ante una alerta real de Defender, la diagnostica
correctamente usando `get_detected_threats`, y tranquiliza al usuario en vez de generar alarma
innecesaria.

**Preparación previa (dentro de la VM, inmediatamente antes de este escenario):**
1. Abre el navegador dentro de la VM y ve a
   `https://www.eicar.org/download-anti-malware-testfile/`.
2. Descarga el fichero de prueba estándar oficial (por ejemplo la variante `eicar.com` o
   `eicar_com.txt` que ofrece la propia página) directamente desde ese sitio.
   > **Importante:** la cadena EICAR **no** se escribe en ningún fichero de este repositorio.
   > Cualquier fichero que la contenga será puesto en cuarentena por Defender — es exactamente el
   > efecto que se busca en este escenario, así que el fichero debe descargarse en el momento, dentro
   > de la VM, desde la fuente oficial.
   > **Si el navegador bloquea la descarga** (ocurrió en la prueba en la VM del 24/10/2026): copia
   > la cadena de 68 caracteres que publica la propia página de EICAR y escríbela en un fichero
   > desde PowerShell, fuera del repositorio, con `Set-Content` y `-Encoding ascii` en `$env:TEMP`.
   > La cadena se copia en el momento desde la fuente oficial y **no** se guarda en este documento.
3. Espera unos segundos: Windows Defender detecta el fichero al escribirse a disco (protección en
   tiempo real) y lo pone en cuarentena automáticamente, sin intervención del agente. La detección
   queda en el historial de Defender, que es lo que lee `get_detected_threats`: no hace falta
   repetir EICAR si ya se generó antes.

**Frase exacta a escribir (tras la detección):**
```
me ha saltado una alerta, ¿es grave?
```

**Comportamiento esperado.** El agente llama a `get_detected_threats` (lectura, sin confirmación),
recibe en `data` el registro de la amenaza detectada por Defender, identifica por el nombre de la
amenaza (típicamente algo como `Virus:DOS/EICAR_Test_File` o similar) que se trata del fichero de
prueba estándar de la industria antivirus, y responde explicando:
- Que no es un virus real, sino el fichero de prueba oficial usado para verificar que un antivirus
  funciona.
- Que Defender ya lo ha detectado y puesto en cuarentena automáticamente.
- Que no hay ninguna acción adicional que el usuario deba tomar.

**Qué demuestra al tribunal.** Que el agente consulta datos reales del sistema (no inventa nada, tal y
como exige el `SYSTEM_PROMPT`), que interpreta correctamente el contenido de una alerta real sin
generar pánico, y que el tono de la respuesta es el de un asistente doméstico claro y sin alarmismo.

**Advertencias observadas en la prueba en la VM.**
- Empieza cada escenario en una conversación nueva (`F5` o «Empezar una conversación nueva»): el
  historial se acumula y, con el plan gratuito de Groq, una conversación larga puede superar el
  límite de 8.000 tokens por minuto (error 413; la salida de cada herramienta ya se recorta a 6.000
  caracteres, INC-08).
- En la prueba, la respuesta del modelo también habló del estado de Defender y afirmó que las firmas
  estaban «al día» cuando tenían 402 días: el modelo no sabe leer las fechas `/Date(…)/` (INC-12, sin
  corregir). Si se muestra este escenario, conviene no detenerse en esa parte o contrastarla con la
  barra lateral, que sí calcula bien la antigüedad de las firmas.

## 4. Escenario 3 · Refuerzo con humano en el bucle

**Objetivo.** Demostrar que ninguna operación de nivel "mutante" se ejecuta sin una confirmación
explícita del usuario mediante un clic, y que el resultado se verifica después.

**Preparación previa.** Ninguna: el snapshot «Demo lista» ya deja el perfil "Private" del firewall
desactivado (ver sección 0, paso 3).

**Frase exacta a escribir:**
```
revisa mi firewall
```

**Comportamiento esperado.**
1. El agente llama a `get_firewall_status` (lectura) y detecta que el perfil "Private" está
   desactivado.
2. El agente propone ejecutar `set_firewall_profile` con `profile=Private`, `enabled=True`. En
   Streamlit aparece una burbuja de chat con: la descripción de la herramienta ("Activa o desactiva un
   perfil concreto del firewall de Windows"), el bloque JSON con los parámetros propuestos, el badge de
   nivel **🔴 Mutante**, y dos botones lado a lado: **"✅ Confirmar"** y **"❌ Cancelar"**. El turno
   queda bloqueado ahí — el agente no hace nada más hasta que se pulsa un botón.
3. Pulsa **"✅ Confirmar"**.
4. La operación se ejecuta (la terminal elevada anclada es lo que permite que `requiere_admin=True` no
   bloquee la ejecución) y el agente informa del resultado.
5. El semáforo de la barra lateral se refresca automáticamente tras la mutación.
6. Para el cierre del ciclo, escribe de nuevo:
   ```
   revisa mi firewall otra vez
   ```
   El agente vuelve a llamar a `get_firewall_status` y debe confirmar que el perfil "Private" ya está
   activo.

**Observado en la prueba en la VM (24/10/2026).** Con esa frase exacta el modelo comprobó el estado y
explicó que el perfil estaba desactivado, pero **no propuso la acción**: hizo falta escribir a
continuación `sí, activa el perfil Privado` para que apareciera la tarjeta de confirmación. El
comportamiento depende del modelo y no está garantizado; para la grabación conviene tener preparada
esa segunda frase (o usar directamente `revisa mi firewall y actívalo si hace falta`, sin probar).
El resultado de la prueba (cancelación, confirmación, verificación y auditoría) consta en
`docs/memoria/evidencias/vm/vm_00_notas.md` y en `capturas/vm_09`–`vm_14`.

**Qué demuestra al tribunal.** Que las herramientas de nivel "mutante" quedan bloqueadas hasta un gesto
explícito del usuario (regla innegociable #3 de CLAUDE.md), que la propuesta se muestra con total
transparencia antes de ejecutarse (herramienta, descripción y parámetros exactos), y que el sistema
verifica por sí mismo el efecto de la mutación en vez de asumir que funcionó.

## 5. Plan B — vídeo grabado

Si algo falla en directo (conexión, proveedor LLM, VM), se reproduce un vídeo grabado previamente en
lugar de la demo en vivo.

**Cómo grabarlo:**
1. Restaura el snapshot «Demo lista» justo antes de grabar (mismo estado que usará la demo en vivo).
2. Usa un grabador de pantalla dentro de la VM (el Grabador de Windows integrado, o OBS Studio si está
   instalado) a resolución 1920×1080 o superior, con audio del micrófono activado para narrar en
   español lo que se está escribiendo y lo que responde el agente.
3. Graba **en una sola toma continua**, sin cortes, siguiendo el guion en este orden exacto:
   1. Escenario 1 · Diagnóstico (sección 2).
   2. Escenario 2 · Amenaza real segura — EICAR (sección 3), incluyendo la descarga del fichero desde
      eicar.org y la detección automática de Defender.
   3. Escenario 3 · Refuerzo con humano en el bucle (sección 4), incluyendo el clic en "✅ Confirmar" y
      la verificación final.
4. Detén la grabación tras la verificación final del Escenario 3.
5. Exporta el vídeo fuera de la VM (carpeta compartida o USB) y guárdalo en el equipo desde el que se
   hará la defensa.
6. Reprodúcelo entero al menos una vez antes de la defensa para comprobar que el audio y el vídeo están
   sincronizados y que se ve con claridad.
