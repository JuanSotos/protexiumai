# ProtexiumAI

ProtexiumAI es un asistente de seguridad conversacional para Windows 11 dirigido al usuario doméstico, desarrollado como Trabajo de Fin de Grado. El usuario pregunta en lenguaje natural (por ejemplo, «¿cómo está mi PC?» o «me salió una alerta rara») y el sistema diagnostica, explica y actúa sobre Windows Defender y el firewall mediante cmdlets de PowerShell, siempre con confirmación humana para cualquier acción que modifique el sistema.

El prototipo cubre tres módulos: diagnóstico en lenguaje natural, respuesta guiada ante incidentes e integración con Windows.

## Estado actual

Documentación de la entrega intermedia en preparación (fase P10, parcial: faltan las evidencias de las pruebas en máquinas virtuales). Hay 3 funcionalidades completadas, 4 en curso y 20 pendientes de las 27 planificadas (F01–F27). El detalle, con el estado y el origen de cada una, está en [`docs/memoria/ESTADO_FUNCIONALIDADES.md`](docs/memoria/ESTADO_FUNCIONALIDADES.md).

Lo que existe hoy:

- Agente conversacional con *function calling* y proveedor LLM dual: Groq (nube) u Ollama (local, «modo privado»).
- Capa ejecutora con 25 herramientas cerradas (17 de lectura, 4 de acción y 4 mutantes) sobre Windows Defender y el firewall, con confirmación humana y auditoría total.
- Catálogo YAML validado como única fuente de verdad de las herramientas (`catalogo/`).
- Detección de plataforma y capacidades del equipo, que filtra las herramientas que se ofrecen al LLM.
- Interfaz de consola (`cli.py`) e interfaz gráfica con Streamlit.
- 454 tests automáticos (subprocess y LLM simulados) con una cobertura de `src/` del 96 %.

Lo que **no** existe todavía (ver [Limitaciones conocidas](#limitaciones-conocidas)): comprobaciones de línea base CIS, Linux, remediación reversible, perfiles, enrutador de privacidad, análisis de procesos y persistencia, e instaladores.

## Requisitos

- Windows 11 (el único sistema con soporte funcional por ahora).
- Python 3.11 o superior. La batería de tests se ha ejecutado con Python 3.14.
- Git, porque uno de los tests (`tests/test_repo_sin_secretos.py`) consulta el índice del repositorio.
- PowerShell de Windows (viene con el sistema).
- Para usar el proveedor en la nube, una clave de API de Groq. Para el modo privado, [Ollama](https://ollama.com) (ver más abajo).
- Para ejecutar herramientas de acción o mutantes, una terminal **elevada**. El código nunca intenta elevar privilegios por su cuenta: si falta el permiso, devuelve un error explicativo.

## Instalación (Windows)

Desde la raíz del repositorio, en PowerShell:

1. Crear el entorno virtual:

   ```powershell
   python -m venv venv
   ```

2. Activarlo:

   ```powershell
   venv\Scripts\Activate.ps1
   ```

   Si PowerShell bloquea el script por la directiva de ejecución, se puede permitir solo para esa ventana con `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned`.

3. Instalar las dependencias de ejecución:

   ```powershell
   pip install -r requirements.txt
   ```

4. Para ejecutar los tests, instalar además las de desarrollo (incluyen `requirements.txt`, `pytest` y `pytest-cov`):

   ```powershell
   pip install -r requirements-dev.txt
   ```

Las dependencias no tienen la versión fijada. Los 454 tests pasan tanto en el entorno de desarrollo como en una instalación nueva desde un clon limpio del repositorio.

## Configuración

1. Copiar la plantilla:

   ```powershell
   copy .env.example .env
   ```

2. Editar `.env`:

   | Variable | Para qué sirve |
   |---|---|
   | `GROQ_API_KEY` | Clave de API de Groq. Obligatoria si `LLM_PROVIDER=groq`. |
   | `LLM_PROVIDER` | `groq` (nube, valor por defecto) u `ollama` (local). |
   | `LLM_MODEL` | Modelo a usar con Ollama (por defecto `llama3.2:3b`). Con Groq se ignora. |
   | `LLM_BASE_URL` | URL base de Ollama (por defecto `http://localhost:11434/v1`). Con Groq se ignora. |

   Con Groq el modelo va fijo en `src/config.py` (`openai/gpt-oss-20b`, con `reasoning_effort="low"`).

`.env.example` no contiene ninguna clave real. `.env` está en `.gitignore` y nunca debe subirse al repositorio; un test (`tests/test_repo_sin_secretos.py`) lo vigila. El proyecto no pide, procesa ni almacena contraseñas del usuario.

## Modo privado con Ollama

Con `LLM_PROVIDER=ollama` el cliente LLM apunta a Ollama (por defecto `http://localhost:11434/v1`) en vez de a Groq. Ninguna llamada sale hacia servicios de internet: la conversación y los datos que devuelven las herramientas se procesan en la máquina donde corre Ollama.

1. Instalar Ollama:

   ```powershell
   winget install Ollama.Ollama
   ```

2. Descargar el modelo por defecto:

   ```powershell
   ollama pull llama3.2:3b
   ```

3. Comprobar que Ollama responde y que el modelo está descargado:

   ```powershell
   python scripts/check_local.py
   ```

4. Activar el modo privado de una de estas dos formas:
   - En `.env`: `LLM_PROVIDER=ollama` (y, si se quiere, `LLM_MODEL` y `LLM_BASE_URL`).
   - En la interfaz gráfica: elegir «Local (Ollama)» en el selector «Proveedor LLM» de la barra lateral. Mientras esté activo se muestra el aviso «Modo local activo: nada sale de este equipo.».

**Qué se ha verificado y qué no.** En la fase P5 se verificó de extremo a extremo, con `llama3.2:3b`, una sesión de 10 turnos con las 7 herramientas que había entonces: el modelo eligió la herramienta correcta y generó argumentos JSON válidos en 13 de 14 llamadas, y el único fallo (un parámetro no declarado) fue rechazado por el validador de `src/executor.py` sin llegar a PowerShell. Esa verificación **no se ha repetido** con las 25 herramientas actuales. Con un modelo tan pequeño, la narración del turno puede describir mal el resultado de una acción cancelada; el estado real de cada herramienta («ejecutada» o «cancelada», «éxito» o «error») se muestra aparte en la CLI y en Streamlit, y `logs/audit.jsonl` es la fuente de verdad.

### Ollama en el anfitrión y ProtexiumAI en la máquina virtual

Las pruebas con efectos se hacen en la VM (ver [más abajo](#pruebas-con-efectos-solo-en-máquinas-virtuales)), pero Ollama solo hace falta instalarlo en el anfitrión:

1. En el anfitrión, arrancar Ollama escuchando en todas las interfaces:

   ```powershell
   $env:OLLAMA_HOST = "0.0.0.0"
   ollama serve
   ```

2. En la VM, en `.env`, apuntar al anfitrión a través del *gateway* NAT de VirtualBox:

   ```
   LLM_PROVIDER=ollama
   LLM_BASE_URL=http://10.0.2.2:11434/v1
   ```

3. Verificar la conexión desde la VM con `python scripts/check_local.py`.

## Ejecución

Chat por consola (escribir `salir` para terminar; cada acción que modifica el sistema pide confirmación `s/n`):

```powershell
python cli.py
```

Interfaz gráfica (se abre en `http://localhost:8501`):

```powershell
streamlit run app/streamlit_app.py
```

Para que las herramientas de acción y mutantes puedan ejecutarse, lanzar la terminal **como administrador**, y solo en la máquina virtual de pruebas. Las herramientas de lectura funcionan sin elevar.

Otros comandos:

```powershell
python -m src.plataforma            # diagnóstico JSON de las capacidades detectadas del equipo
python scripts/hello_ps.py          # verificación de PowerShell
python scripts/hello_llm.py         # verificación del proveedor LLM
python scripts/check_local.py       # verificación del modo privado (Ollama)
python scripts/verificar_whitelist.py  # comprueba que nada fuera del catálogo se puede ejecutar
```

## Tests y cobertura

Todos los tests usan `subprocess` y el cliente LLM simulados: no ejecutan acciones reales sobre el sistema, no necesitan `.env` ni conexión y se pueden lanzar en cualquier equipo.

```powershell
python -m pytest
```

Con cobertura de `src/` y parte JUnit:

```powershell
python -m pytest --cov=src --cov-report=term-missing --junitxml=docs/memoria/evidencias/P10_junit.xml
```

El parte JUnit incluye el nombre del equipo (`hostname=`) y los identificadores de los casos con claves sintéticas del test de secretos, que hacen fallar a ese mismo test si el XML queda en el repositorio: antes de versionarlo hay que anonimizarlo, como se hizo con `P10_junit.xml` (ver `docs/memoria/PRUEBAS.md`, P10).

Resultado de la batería final de la entrega intermedia (P10): 454 pasan, 0 fallan; cobertura total de `src/` del 96 % (`src/catalogo.py` 97 %, `src/executor.py` 95 %, `src/tools_schema.py` 100 %, `src/plataforma/deteccion.py` 97 %). La salida íntegra está en [`docs/memoria/evidencias/P10_pytest_final.txt`](docs/memoria/evidencias/P10_pytest_final.txt). La vista de Streamlit (`app/streamlit_app.py`) no tiene tests automáticos.

## Estructura del repositorio

```
CLAUDE.md                  Reglas de seguridad y convenciones del proyecto
CHANGELOG.md               Historial de cambios por fase (P0–P10)
cli.py                     Chat por consola
app/                       Interfaz Streamlit y módulos de apoyo (textos, lecturas, auditoría, cliente observado)
catalogo/                  Catálogo YAML: única fuente de verdad de herramientas y comprobaciones
  _ESQUEMA.md                Esquema, aplicabilidad, lista de denegación y presupuesto de tokens
  herramientas_llm.yaml      Las 25 herramientas que ve el LLM
  mapeo_marcos.csv           Mapeos a CIS/CCN/ATT&CK/ENS (solo con verificación de Juan; 14 herramientas mapeadas)
  windows/  linux/           Reservadas para las comprobaciones de H2 y H3 (hoy vacías)
src/
  agent.py                   Bucle del agente: function calling, historial y system prompt
  executor.py                Capa ejecutora: única que lanza PowerShell; validación, niveles y auditoría
  catalogo.py                Cargador y validador estricto del catálogo
  tools_schema.py            Esquema de herramientas del LLM, generado desde el catálogo
  plataforma/                Detección de sistema, edición y capacidades (solo lectura)
  audit.py                   Registro de auditoría en logs/audit.jsonl
  config.py                  Perfiles de proveedor LLM (groq/ollama)
scripts/                   Scripts de verificación manual
tests/                     Batería pytest (con fixtures de os-release en tests/fixtures/)
docs/
  demo_escenarios.md         Guion de la demo para la defensa
  cobertura_windows_security.md  Cobertura de áreas de Windows Security
  memoria/                   Documentación del TFG: estado, cambios, registro de IA, pruebas y evidencias
design_handoff_protexiumai_ui/  Paquete de diseño de la interfaz (referencia, no código de producción)
```

`logs/` (la auditoría), `data/`, `.env` y `venv/` se generan en local y están excluidos del repositorio.

## Documentación de la memoria

Todo en [`docs/memoria/`](docs/memoria/):

- [`ESTADO_FUNCIONALIDADES.md`](docs/memoria/ESTADO_FUNCIONALIDADES.md): estado y origen de F01–F27.
- [`CAMBIOS.md`](docs/memoria/CAMBIOS.md): cambios respecto a la memoria preliminar y decisiones de diseño durante el desarrollo.
- [`REGISTRO_IA.md`](docs/memoria/REGISTRO_IA.md) e [`INCIDENCIAS_IA.md`](docs/memoria/INCIDENCIAS_IA.md): uso de la IA y sus incidencias.
- [`PRUEBAS.md`](docs/memoria/PRUEBAS.md) y [`evidencias/`](docs/memoria/evidencias/): pruebas por fase y salidas de pytest.
- [`DATOS_PARA_MEMORIA.md`](docs/memoria/DATOS_PARA_MEMORIA.md): cifras extraídas del repositorio.
- [`PLANIFICACION_RESTANTE.md`](docs/memoria/PLANIFICACION_RESTANTE.md): borrador de planificación hasta junio de 2027.

## Pruebas con efectos: solo en máquinas virtuales

Las herramientas de acción y mutantes modifican el sistema (escaneos, cuarentena, perfiles del firewall, restauración del firewall). **Toda prueba con efectos reales se ejecuta únicamente en una máquina virtual** (VirtualBox con Windows 11 y un snapshot restaurable «Base limpia»), nunca en el equipo de desarrollo, y la lanza el autor. En el equipo de desarrollo solo se ejecutan los tests simulados y los cmdlets de lectura. El procedimiento de la demo, con el snapshot «Demo lista», está en [`docs/demo_escenarios.md`](docs/demo_escenarios.md).

Para reproducir el proyecto en una VM limpia: clonar el repositorio, seguir [Instalación](#instalación-windows) y [Configuración](#configuración), y ejecutar `python -m pytest`; después, la terminal elevada para las acciones.

## Seguridad

Las reglas de seguridad están en [`CLAUDE.md`](CLAUDE.md). En resumen:

- Todo comando PowerShell pasa por `src/executor.py` y por el catálogo; ningún otro módulo lanza procesos.
- Los comandos se construyen con plantillas fijas y valores de listas cerradas; nada procedente del LLM o del usuario se concatena en un comando.
- Confirmación humana obligatoria para toda herramienta de acción o mutante.
- Toda llamada al executor, aceptada o rechazada, queda registrada en `logs/audit.jsonl`.
- La salida de las herramientas son datos, nunca instrucciones (`tests/test_injection.py`).
- Sin elevación automática y sin credenciales de usuario.

## Limitaciones conocidas

- **Soporte funcional solo en Windows 11 por ahora.** En Windows 10 se detecta la plataforma y se ofrecen las mismas 25 herramientas, pero no se ha probado en ese sistema. En Linux solo funciona la detección de plataforma y capacidades (`python -m src.plataforma`): el agente no ofrece herramientas y lo avisa. La detección en Linux se ha probado únicamente con ficheros `os-release` simulados; falta contrastarla en una VM Linux real.
- Windows Defender: Tamper Protection impide cambiar su configuración, así que no hay herramientas que modifiquen `Set-MpPreference`; las mutaciones actúan sobre el firewall. Con un antivirus de terceros Defender pasa a modo pasivo y el agente lo explica.
- Los mapeos a marcos normativos (CIS, CCN-STIC, ATT&CK, D3FEND, ENS) están rellenados solo para 14 de las 25 herramientas y tres marcos (CIS Controls v8.1, ATT&CK y ENS, verificados por el autor); CIS Benchmark, CCN-STIC y D3FEND siguen sin mapeo: solo valen los que aporte el autor con su verificación.
- Todavía no hay validador con listas de denegación sobre planes, confirmación ligada a un plan, remediación reversible (check/plan/apply/verify/rollback), perfiles Hogar/Sistemas, enrutador por sensibilidad ni anonimizador, comprobaciones CIS, análisis de procesos y persistencia, ni instaladores.
- El motor local integrado (llama-cpp-python) está previsto para H5; hoy el modo privado necesita Ollama instalado aparte.
- Un modelo local pequeño (`llama3.2:3b`) elige peor las herramientas y narra peor los resultados que el modelo de la nube.
- La interfaz de Streamlit no tiene tests automáticos; su revisión es manual.
- Las pruebas manuales en VM están documentadas como procedimiento, pero el repositorio aún no contiene capturas ni registro de resultados (`docs/memoria/evidencias/vm/` y `capturas/` están vacías).
- Las dependencias no tienen la versión fijada.
