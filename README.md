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

## Comandos útiles

```powershell
python -m pytest                    # tests
python cli.py                       # chat por consola
streamlit run app/streamlit_app.py  # interfaz gráfica
python scripts/hello_ps.py          # verificación PowerShell
python scripts/hello_llm.py         # verificación LLM
```
