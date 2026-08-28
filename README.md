# ProtexiumAI

ProtexiumAI es un asistente de seguridad conversacional para Windows 11 dirigido al usuario doméstico, desarrollado como Trabajo de Fin de Grado. El usuario pregunta en lenguaje natural (por ejemplo, "¿cómo está mi PC?" o "me salió una alerta rara") y el sistema diagnostica, explica y actúa sobre Windows Defender y el firewall mediante cmdlets de PowerShell, siempre con confirmación humana para cualquier acción que modifique el sistema.

El prototipo cubre tres módulos: diagnóstico en lenguaje natural, respuesta guiada ante incidentes e integración con Windows.

## Puesta en marcha (Windows)

1. Crear el entorno virtual:

   ```powershell
   python -m venv venv
   ```

2. Activar el entorno virtual:

   ```powershell
   venv\Scripts\Activate.ps1
   ```

3. Instalar las dependencias:

   ```powershell
   pip install -r requirements.txt
   ```

## Configuración

1. Copiar `.env.example` a `.env`:

   ```powershell
   copy .env.example .env
   ```

2. Editar `.env` y rellenar `GROQ_API_KEY` (si se usa el proveedor en la nube) y ajustar `LLM_PROVIDER`, `LLM_MODEL` y `LLM_BASE_URL` según se quiera usar Groq (nube) u Ollama (local, "modo privado").

## Modo privado

Con `LLM_PROVIDER=ollama`, el cliente LLM apunta a `http://localhost:11434/v1` (o al host que se configure) en vez de a Groq. Ninguna llamada sale hacia servicios en internet: la conversación, los datos que devuelven las herramientas de Defender/firewall y el diagnóstico se procesan enteramente en la máquina donde corre Ollama. Se ha verificado de extremo a extremo (incluido function calling) con el modelo `llama3.2:3b`: en una sesión de 10 turnos con las 7 herramientas de la WHITELIST, el modelo eligió la herramienta correcta y generó argumentos JSON válidos en 13 de 14 llamadas; el único fallo (un parámetro no declarado) fue rechazado con seguridad por el validador de `src/executor.py` sin llegar a invocar PowerShell — el mismo comportamiento que tendría cualquier entrada mal formada. No ha sido necesario restringir las herramientas disponibles en este modo.

Con un modelo tan pequeño, la respuesta en lenguaje natural del turno ocasionalmente describe mal el resultado de una acción cancelada (p. ej. dice que ha desactivado un perfil del firewall cuando en realidad el usuario respondió que no). El estado real de cada herramienta no depende de esa narración: tanto `cli.py` como la interfaz de Streamlit muestran, por separado, si la herramienta fue "ejecutada" o "cancelada" y si terminó en éxito o error — y `logs/audit.jsonl` es la fuente de verdad definitiva.

### Instalación de Ollama en Windows

1. Instalar Ollama:

   ```powershell
   winget install Ollama.Ollama
   ```

2. Descargar el modelo usado por defecto en modo privado:

   ```powershell
   ollama pull llama3.2:3b
   ```

3. Comprobar que Ollama está accesible y que el modelo está descargado:

   ```powershell
   python scripts/check_local.py
   ```

### Activar el modo privado

- **Vía `.env`**: fijar `LLM_PROVIDER=ollama` (opcionalmente `LLM_MODEL` y `LLM_BASE_URL` si se usa un modelo o un host distintos de los valores por defecto).
- **Vía la interfaz**: en `streamlit run app/streamlit_app.py`, elegir "Local (Ollama)" en el selector "Proveedor LLM" de la barra lateral. La interfaz muestra el aviso "🔒 Modo local activo: nada sale de este equipo." mientras ese proveedor esté activo.

### Uso desde la máquina virtual de pruebas

Las pruebas de acciones y mutaciones reales se ejecutan en la VM (ver más abajo), pero Ollama solo hace falta instalarlo en el anfitrión:

1. En el anfitrión, arrancar Ollama escuchando en todas las interfaces:

   ```powershell
   $env:OLLAMA_HOST = "0.0.0.0"
   ollama serve
   ```

2. En la VM, editar `.env` para apuntar al anfitrión a través del gateway NAT de VirtualBox:

   ```
   LLM_PROVIDER=ollama
   LLM_BASE_URL=http://10.0.2.2:11434/v1
   ```

3. Verificar la conexión desde dentro de la VM con `python scripts/check_local.py`.

## Comandos útiles

```powershell
python -m pytest                    # tests
python cli.py                       # chat por consola
streamlit run app/streamlit_app.py  # interfaz gráfica
python scripts/hello_ps.py          # verificación PowerShell
python scripts/hello_llm.py         # verificación LLM
python scripts/check_local.py       # verificación modo privado (Ollama)
```
