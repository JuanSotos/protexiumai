# Estado inicial del repositorio (línea base P7)

Inventario de solo lectura generado el 2026-10-22 a partir del código en la rama `master`, antes de cualquier cambio de P7.
Las tablas se han generado importando `src.executor.WHITELIST` y `src.tools_schema`, no transcritas a mano.

## 1. Árbol de módulos

Ficheros versionados (`git ls-files`), con la primera línea del docstring de cada módulo Python.

```
.claude/launch.json
.env.example
.gitignore
.streamlit/config.toml
CLAUDE.md
README.md
app/__init__.py
app/auditoria.py  — Lectura y traducción a llano del registro de auditoría (`logs/audit.jsonl`).
app/cliente_observado.py  — Envoltorio de solo lectura del cliente LLM, para saber cuántas órdenes trae un turno.
app/estilos.css
app/lecturas.py  — Lecturas del equipo para el semáforo y la pantalla "Estado del equipo en detalle".
app/streamlit_app.py  — Interfaz gráfica de ProtexiumAI construida con Streamlit.
app/textos.py  — Tablas de redacción en lenguaje llano de la interfaz.
cli.py  — Chat por consola para interactuar con el agente de ProtexiumAI.
docs/cobertura_windows_security.md
docs/demo_escenarios.md
requirements.txt
scripts/check_local.py  — Script de verificación del modo privado (Ollama): comprueba conectividad y que el modelo esté descargado.
scripts/hello_llm.py  — Script de verificación de la conexión con el proveedor LLM configurado (groq/ollama).
scripts/hello_ps.py  — Script de verificación de la ejecución de comandos PowerShell desde Python.
scripts/verificar_whitelist.py  — Script de demostración: comprueba que es imposible ejecutar nada fuera de la WHITELIST.
src/__init__.py  — Paquete src: contiene la lógica de ProtexiumAI (configuración, executor, auditoría, tools y agente).
src/agent.py  — Bucle del agente conversacional: function calling con el LLM, gestión del historial y system prompt.
src/audit.py  — Registro de auditoría: escribe en logs/audit.jsonl cada llamada al executor (aceptada o rechazada) con timestamp, herramienta, parámetros, proveedor y resultado.
src/config.py  — Carga de variables de entorno (.env) y definición de los perfiles de proveedor LLM (groq/ollama).
src/executor.py  — Capa ejecutora: WHITELIST de cmdlets de PowerShell permitidos, validación de parámetros, niveles de acción y ejecución segura.
src/tools_schema.py  — Definición de las tools para function calling del LLM, generada a partir de la WHITELIST de src/executor.py.
tests/__init__.py  — Paquete tests: pruebas unitarias con pytest, subprocess y LLM mockeados.
tests/conftest.py  — Fixtures compartidas: aíslan los tests de executor/audit del sistema real.
tests/test_agent.py  — Tests de src/agent.py: bucle de function calling, confirmación humana y auditoría de cancelaciones.
tests/test_auditoria.py  — Tests del lector del registro de auditoría (app/auditoria.py).
tests/test_cliente_observado.py  — Tests del envoltorio que cuenta la cola de órdenes de un turno (§8).
tests/test_executor.py  — Tests de src/executor.py: WHITELIST, validación de parámetros y auditoría.
tests/test_injection.py  — Tests de inyección de prompts: verifican que la salida de las herramientas son datos, nunca instrucciones.
tests/test_textos.py  — Tests de las tablas de redacción en llano de la interfaz (app/textos.py).
tests/test_tools_schema.py  — Tests de src/tools_schema.py: el schema de function calling se genera desde executor.WHITELIST.
design_handoff_protexiumai_ui/  — paquete de diseño de la interfaz (9 ficheros versionados)
```

## 2. WHITELIST actual (25 herramientas)

Por nivel — accion: 4, lectura: 17, mutante: 4. Requieren administrador: 12 de 25.

| id | nivel | requiere_admin | parámetros y valores permitidos | plantilla |
|---|---|---|---|---|
| `get_defender_status` | lectura | no | — | `Get-MpComputerStatus \| Select-Object AMServiceEnabled, AntispywareEnabled, AntivirusEnabled, RealTimeProtectionEnabled, NISEnabled, AntivirusSignatureLastUpdated, AntispywareSignatureLastUpdated, QuickScanEndTime, FullScanEndTime, ComputerState \| ConvertTo-Json` |
| `get_detected_threats` | lectura | no | — | `Get-MpThreatDetection \| ConvertTo-Json -Depth 3` |
| `get_firewall_status` | lectura | no | — | `Get-NetFirewallProfile \| Select-Object Name, Enabled, AllowInboundRules, NotifyOnListen \| ConvertTo-Json` |
| `get_active_network_profile` | lectura | no | — | `Get-NetConnectionProfile \| Select-Object Name, InterfaceAlias, NetworkCategory \| ConvertTo-Json` |
| `start_quick_scan` | accion | sí | — | `Start-MpScan -ScanType QuickScan` |
| `update_signatures` | accion | sí | — | `Update-MpSignature` |
| `set_firewall_profile` | mutante | sí | `profile`: `Domain`, `Private`, `Public`<br>`enabled`: `True`, `False` | `Set-NetFirewallProfile -Profile {profile} -Enabled {enabled}` |
| `set_block_all_incoming` | mutante | sí | `profile`: `Domain`, `Private`, `Public`<br>`allow_inbound_rules`: `True`, `False` | `Set-NetFirewallProfile -Profile {profile} -AllowInboundRules {allow_inbound_rules}` |
| `remove_all_threats` | mutante | sí | — | `Remove-MpThreat` |
| `get_account_info` | lectura | no | — | `$p = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent()); [PSCustomObject]@{ Usuario = $p.Identity.Name; EsAdministradorLocal = $p.IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator) } \| ConvertTo-Json` |
| `start_full_scan` | accion | sí | — | `Start-MpScan -ScanType FullScan` |
| `start_custom_scan` | accion | sí | `ruta`: `Descargas`, `Escritorio`, `Documentos` | `$rutas = @{{ 'Descargas' = "$env:USERPROFILE\Downloads"; 'Escritorio' = "$env:USERPROFILE\Desktop"; 'Documentos' = "$env:USERPROFILE\Documents" }}; Start-MpScan -ScanType CustomScan -ScanPath $rutas['{ruta}']` |
| `get_allowed_threats` | lectura | no | — | `Get-MpPreference \| Select-Object ThreatIDDefaultAction_Ids, ThreatIDDefaultAction_Actions \| ConvertTo-Json` |
| `get_defender_exclusions` | lectura | sí | — | `Get-MpPreference \| Select-Object ExclusionPath, ExclusionExtension, ExclusionProcess \| ConvertTo-Json` |
| `get_defender_preferences` | lectura | no | — | `Get-MpPreference \| Select-Object EnableControlledFolderAccess, MAPSReporting, SubmitSamplesConsent, PUAProtection \| ConvertTo-Json` |
| `get_exploit_protection_status` | lectura | no | — | `Get-ProcessMitigation -System \| ConvertTo-Json -Depth 4` |
| `get_allowed_firewall_rules` | lectura | no | — | `Get-NetFirewallRule -Direction Inbound -Action Allow -Enabled True \| Select-Object DisplayName, Profile \| ConvertTo-Json` |
| `restore_firewall_defaults` | mutante | sí | — | `netsh advfirewall reset \| Out-Null` |
| `get_core_isolation_status` | lectura | no | — | `Get-CimInstance -Namespace root\Microsoft\Windows\DeviceGuard -ClassName Win32_DeviceGuard \| ConvertTo-Json -Depth 3` |
| `get_secure_boot_status` | lectura | sí | — | `try { [PSCustomObject]@{ SecureBootEnabled = (Confirm-SecureBootUEFI) } \| ConvertTo-Json } catch { [PSCustomObject]@{ SecureBootEnabled = $null; Error = $_.Exception.Message } \| ConvertTo-Json }` |
| `get_tpm_status` | lectura | sí | — | `Get-Tpm \| Select-Object TpmPresent, TpmReady, TpmEnabled, TpmActivated, ManufacturerIdTxt, ManufacturerVersion \| ConvertTo-Json` |
| `get_bitlocker_status` | lectura | sí | — | `Get-BitLockerVolume \| Select-Object MountPoint, VolumeStatus, ProtectionStatus, EncryptionPercentage \| ConvertTo-Json` |
| `get_storage_status` | lectura | no | — | `Get-Volume \| Where-Object { $_.DriveLetter } \| Select-Object DriveLetter, FileSystemLabel, SizeRemaining, Size \| ConvertTo-Json` |
| `get_battery_status` | lectura | no | — | `Get-CimInstance -ClassName Win32_Battery \| Select-Object EstimatedChargeRemaining, BatteryStatus \| ConvertTo-Json` |
| `get_time_service_status` | lectura | no | — | `Get-Service -Name W32Time \| Select-Object Status, StartType \| ConvertTo-Json` |

## 3. Tests

Total recogido por `pytest --collect-only`: **185 tests** en 7 ficheros.

| fichero | tests |
|---|---|
| `tests/test_agent.py` | 16 |
| `tests/test_auditoria.py` | 26 |
| `tests/test_cliente_observado.py` | 8 |
| `tests/test_executor.py` | 99 |
| `tests/test_injection.py` | 3 |
| `tests/test_textos.py` | 24 |
| `tests/test_tools_schema.py` | 9 |

## 4. Batería base

Comando: `python -m pytest -q`. Salida íntegra en `docs/memoria/evidencias/P07_pytest_baseline.txt`.

Resultado: **185 passed in 3.82s**, 0 fallos, 0 errores. No hay tests fallidos que anotar.

## 5. Proveedor LLM y dependencias

- Proveedor por defecto (`src/config.py`, `LLM_PROVIDER` ausente): `groq`.
- Groq (nube): base_url `https://api.groq.com/openai/v1`, modelo `openai/gpt-oss-20b` fijo en código; `src/agent.py` añade `reasoning_effort="low"` solo cuando el proveedor es `groq`.
- Ollama (local): base_url por defecto `http://localhost:11434/v1`, modelo por defecto `llama3.2:3b` (sobrescribibles con `LLM_BASE_URL` y `LLM_MODEL`).
- `.env.example` (sin valores secretos):

```
# Copia este archivo a .env y rellena los valores reales. .env nunca se sube al repositorio.

# Clave de API de Groq (proveedor en la nube). Requerida si LLM_PROVIDER=groq.
GROQ_API_KEY=

# Proveedor LLM activo: groq (nube) u ollama (local, "modo privado")
LLM_PROVIDER=groq

# Modelo a usar cuando LLM_PROVIDER=ollama (con groq se ignora: el modelo va fijo en src/config.py)
LLM_MODEL=llama3.2:3b

# URL base a usar cuando LLM_PROVIDER=ollama (con groq se ignora: la URL va fija en src/config.py)
LLM_BASE_URL=http://localhost:11434/v1
```

- `requirements.txt`: `openai`, `streamlit`, `python-dotenv`, `pytest` (sin versiones fijadas).

## 6. Observaciones

Detectadas durante el inventario (no son fallos de la batería):

- `.gitignore` no cubría `.venv/`, `data/`, `*.jsonl`, `.coverage` ni `htmlcov/`. Se completa en P7.
- `pytest-cov` no está instalado en el entorno virtual `venv/`; se declara en `requirements-dev.txt` (P7) pero no se ha instalado.
- El modelo de Groq ya era `openai/gpt-oss-20b` con `reasoning_effort="low"` antes de P7 (introducido en el commit `76ffdcd`, P3). Quedaban referencias obsoletas a `llama-3.3-70b-versatile` en `scripts/hello_llm.py` (corregida en P7) y en `CLAUDE.md` (sección «Arquitectura», no modificada en P7 por no formar parte de las reglas; pendiente de decisión de Juan).
- `README.md` sigue hablando de «7 herramientas de la WHITELIST»; la WHITELIST actual tiene 25.
- `cargar_perfil()` de `src/config.py` no tiene tests: los tests existentes solo construyen la dataclass `PerfilLLM` a mano (`tests/test_agent.py`, `tests/test_injection.py`, `tests/test_textos.py`). Por eso F02 (proveedor dual) se marca «en curso» en `ESTADO_FUNCIONALIDADES.md`.
