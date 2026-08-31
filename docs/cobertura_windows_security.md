# Cobertura de los grupos de Windows Security

Este documento hace seguimiento, grupo a grupo (según la app Windows Security de Windows 11),
de qué opciones cubre la WHITELIST de ProtexiumAI (`src/executor.py`) y cuáles quedan fuera de
alcance a propósito, con la justificación técnica de cada decisión. Se actualiza a medida que se
revisa cada grupo.

Los ocho grupos de la app Windows Security son: Virus & threat protection, Account protection,
Firewall & network protection, App & browser control, Device security, Device performance &
health, Family options y Protection history.

## Grupo 1 — Virus & threat protection

**Cubierto:** `get_defender_status`, `get_detected_threats`, `start_quick_scan`,
`update_signatures`, `remove_all_threats`.

**Pendiente (viable, no implementado todavía):** Full Scan, Custom Scan sobre carpetas
predefinidas, Offline Scan, consulta de amenazas permitidas, consulta de exclusiones
configuradas, consulta de Controlled Folder Access / Cloud-delivered protection / Automatic
sample submission (todo de solo lectura vía `Get-MpPreference`).

**Fuera de alcance por diseño:** cualquier mutación de preferencias de Defender
(`Set-MpPreference`, `Add-MpPreference`, `Remove-MpPreference`) — Tamper Protection de Windows 11
las bloquea, y CLAUDE.md ya excluye `Set-MpPreference` de la WHITELIST por esa razón. Tampoco se
cubre "Ransomware Data Recovery" (integración con OneDrive, fuera del dominio Defender/firewall
del proyecto).

## Grupo 2 — Account protection

**Cubierto:** `get_account_info` — consulta el nombre de la cuenta de Windows con la que se ha
iniciado sesión y si pertenece al grupo de administradores locales (`lectura`, sin parámetros,
sin necesidad de admin).

**Fuera de alcance por diseño — el resto del grupo completo:**

| Opción de la UI | Por qué no se cubre |
|---|---|
| Estado de la cuenta Microsoft / gestión de la cuenta | Es un enlace a `account.microsoft.com` y a la app Configuración, no expone estado consultable de forma fiable vía PowerShell (distinguir cuenta Microsoft vs. local requiere registro o `dsregcmd`, sin cmdlet oficial soportado) |
| Windows Hello (PIN, reconocimiento facial, huella, llave de seguridad) | Se configura mediante un asistente gráfico de enrolamiento biométrico en la app Configuración; no existe un cmdlet oficial para leer o activar estos métodos. Además, son factores de autenticación — tratarlos entra en tensión con la regla innegociable #8 de CLAUDE.md ("sin credenciales") |
| Dynamic lock | El toggle vive en el registro (`HKCU:\...`), sin cmdlet oficial equivalente a `Get/Set-MpPreference` o `Get/Set-NetFirewallProfile` |

**Motivo general:** a diferencia de Defender y el firewall, "Account protection" no tiene una
capa de cmdlets de PowerShell oficial y estable. Forzar su automatización implicaría leer/escribir
claves de registro no documentadas o acercarse a la gestión de credenciales/biometría, lo que
excede tanto el dominio declarado del proyecto ("Windows Defender y el firewall", ver CLAUDE.md)
como su regla de no tocar credenciales. Por eso se ha añadido una única herramienta puramente
informativa (`get_account_info`) que aporta contexto útil — quién ha iniciado sesión y si tiene
privilegios de administrador local, relevante para saber si las herramientas de nivel
accion/mutante podrán ejecutarse — sin entrar en ninguno de los puntos anteriores.

## Grupo 3 — Firewall & network protection

**Cubierto:** `get_firewall_status` (estado de los tres perfiles, si bloquean por completo las
conexiones entrantes y si notifican al bloquear una app), `set_firewall_profile` (activa/desactiva
un perfil), `get_active_network_profile` (qué perfil está activo ahora mismo y en qué red),
`set_block_all_incoming` (bloquea o restaura todas las conexiones entrantes de un perfil, incluidas
las de la lista de apps permitidas), `get_allowed_firewall_rules` (consulta de solo lectura de las
reglas de entrada habilitadas y permitidas) y `restore_firewall_defaults` (restaura todas las
reglas del firewall a los valores de fábrica; acción de alto impacto marcada como tal).

**Fuera de alcance por diseño:** "Allow an app through firewall" (crear reglas nuevas por app o
puerto — requiere texto libre incompatible con el patrón de plantilla fija + enum cerrado);
"Advanced settings" (reglas inbound/outbound arbitrarias, IPsec, monitorización — dominio
demasiado amplio y de alto riesgo); el asistente de diagnóstico de red (sin cmdlet equivalente).

## Grupo 4 — App & browser control

**Cubierto:** bloqueo de apps potencialmente no deseadas, mediante la ampliación de
`get_defender_preferences` (grupo 1) con el campo `PUAProtection` de `Get-MpPreference` — es en
realidad una preferencia de Defender, no una herramienta propia; y `get_exploit_protection_status`
(consulta de solo lectura, sin admin, de la configuración de Exploit Protection a nivel de
sistema — DEP, ASLR, CFG, SEHOP y el resto de mitigaciones vía `Get-ProcessMitigation -System`).

**Fuera de alcance por diseño:** Smart App Control (sin cmdlet oficial, y desactivarlo es
irreversible sin reinstalar Windows); SmartScreen for Microsoft Edge (configuración del
navegador, no de Defender/firewall); "Check apps and files" (vive en registro, sin cmdlet
equivalente a `Get/Set-MpPreference`); Enhanced Phishing Protection — password reuse warning,
detección de contraseñas en editores de texto, análisis de contenido sospechoso (sin cmdlet
estable y cerca del terreno de credenciales); SmartScreen for Microsoft Store Apps (sin cmdlet
Defender/firewall equivalente); la variante por programa de Exploit Protection
(`Get-ProcessMitigation -Name {proceso}` requeriría texto libre o una lista cerrada de procesos
instalados, inviable de mantener como enum); importar/exportar y mutar mitigaciones de Exploit
Protection (`Set-ProcessMitigation` puede romper compatibilidad de apps instaladas).

## Grupo 5 — Device security

**Cubierto:** `get_core_isolation_status` (estado de Core isolation —integridad de
memoria/HVCI, Credential Guard, System Guard— vía `Get-CimInstance` sobre la clase WMI oficial de
Device Guard; `lectura`, sin admin: comprobado en real, devuelve datos completos sin elevar),
`get_secure_boot_status` (si el arranque seguro está activo, vía `Confirm-SecureBootUEFI` con
try/catch para no fallar en BIOS heredada; `lectura`, con admin: comprobado en real, sin elevar
la excepción de acceso denegado queda enmascarada como un JSON válido con el valor a `null`),
`get_tpm_status` (estado del procesador de seguridad/TPM —presente, listo, activado,
fabricante/versión— vía `Get-Tpm`; `lectura`, con admin: comprobado en real, sin elevar devuelve
los seis campos a `null` en vez de un error, lo que ocultaría el estado real) y
`get_bitlocker_status` (estado de cifrado de dispositivo de los volúmenes vía
`Get-BitLockerVolume`; `lectura`, con admin: comprobado en real, sin elevar el cmdlet falla con
"Acceso denegado" sin producir salida, lo que la normalización de lista convertiría en un falso
"sin volúmenes").

**Fuera de alcance por diseño:** Kernel DMA protection y Firmware protection (sin cmdlet oficial
fiable); LSA protection (solo vía registro, sin cmdlet dedicado); Microsoft Vulnerable Driver
Blocklist (automático, sin cmdlet de consulta claro); la insignia compuesta "Secured-core PC" (es
un estado derivado de las otras lecturas, no necesita herramienta propia); y **cualquier
mutación** (activar/desactivar Memory integrity, LSA protection, Credential Guard, o cifrar con
BitLocker) — todas requieren reinicio para aplicarse, y varias debilitarían defensas
fundamentales del sistema, lo que contradice el propósito protector del asistente.

## Grupo 6 — Device performance & health

**Cubierto:** capacidad de almacenamiento (`get_storage_status`, vía `Get-Volume`; `lectura`,
sin admin: comprobado en real, con normalización de lista para el caso de una sola unidad),
estado y carga estimada de la batería (`get_battery_status`, vía `Get-CimInstance
Win32_Battery`; `lectura`, sin admin: comprobado en real, con manejo explícito de "equipo de
sobremesa sin batería" como `data=None`, nunca como un error) y estado del servicio de hora de
Windows (`get_time_service_status`, vía `Get-Service W32Time`; `lectura`, sin admin: comprobado
en real). Las tres de solo lectura, sin parámetros.

**Fuera de alcance por diseño:** "Apps and software" (sin cmdlet oficial sin dependencias
nuevas); informe completo de salud de batería (depende de `powercfg /batteryreport`, sin
estructura JSON limpia); "Fresh start" (reinstalación destructiva de Windows); "liberar espacio
en disco"/Storage Sense (puede borrar datos del usuario); forzar resincronización horaria (bajo
valor para un asistente doméstico).

## Grupo 7 — Family options

**Cubierto:** nada, y no lo habrá — ver más abajo.

**Fuera de alcance por diseño — el grupo completo:** la página "Family options" de Windows
Security no contiene ningún toggle local; es un enlace a `family.microsoft.com`. Toda la
funcionalidad real (informes de actividad, filtros de contenido, límites de tiempo de pantalla,
control de gasto, gestión de dispositivos) vive en el servicio en la nube Microsoft Family
Safety, ligado a un grupo familiar de cuentas Microsoft. No existe ningún cmdlet de PowerShell
local que lea o escriba este estado; depende de un grupo familiar configurado (no aplicable a un
usuario individual); y trata datos de otra persona (normalmente un menor), un ámbito de
privacidad y responsabilidad distinto al de "diagnosticar y proteger mi propio PC" que no cubre
ni siquiera la regla "sin credenciales" de CLAUDE.md porque el problema no son las credenciales,
es el alcance completo del dato. No hay ningún candidato viable ni prompt de implementación para
este grupo.

## Grupo 8 — Protection history

**Cubierto (por herencia de otros grupos):** el historial de amenazas detectadas/en cuarentena ya
lo cubre `get_detected_threats` (grupo 1); la eliminación masiva de amenazas ya la cubre
`remove_all_threats` (grupo 1).

**Pendiente (viable, ya asignado al grupo 1, no ejecutado todavía):** "Allowed threats page" —
consulta de amenazas permitidas explícitamente por el usuario, vía `get_allowed_threats`
(`Get-MpPreference` / `Get-MpThreatCatalog`). No se crea una herramienta nueva específica para
este grupo: es la misma pieza pendiente que ya se identificó en el grupo 1.

**Pendiente de decisión explícita (no implementar sin más):** eliminar una amenaza concreta por
ID (`Remove-MpThreat -ThreatID {id}`) en vez de todas a la vez. El ID de amenaza es un valor
dinámico por sistema, no un enum cerrado, y la regla innegociable #2 de CLAUDE.md exige que todo
parámetro se valide contra una lista cerrada — un ThreatID no encaja ahí. Implementarlo requiere
que Juan decida explícitamente cómo (o si) se relaja esa regla para este caso concreto; no se
resuelve con una validación alternativa (regex, tipo numérico) tomada unilateralmente durante una
tarea de implementación.

**Fuera de alcance por diseño, de forma permanente (no solo "por ahora"):**

| Opción de la UI | Por qué no |
|---|---|
| **Restore** (reintroducir en el equipo un archivo que estaba en cuarentena) | Sin cmdlet oficial documentado de forma estable (requeriría el proveedor CIM `MSFT_MpThreat` vía `Invoke-CimMethod`, poco documentado y dependiente de versión), y sobre todo, reintroduce deliberadamente malware en el disco — lo contrario del propósito del asistente |
| **Allow on device / Allow** (marcar una amenaza detectada como excepción permanente) | Le pediría a Defender que deje de detectar algo que él mismo identificó como amenaza. Es el mismo patrón de acción que ya prueba `tests/test_injection.py` como vector de ataque (un nombre de amenaza manipulado que intenta lograr que el agente "permita" la propia amenaza) — ofrecerla como herramienta real, aunque esté detrás de confirmación humana, aumenta la superficie de ataque sin necesidad real |
| Notificaciones de "servicio importante desactivado" como evento propio | Ya cubierto indirectamente por `get_defender_status` y por `get_defender_preferences` (pendiente del grupo 1); no necesita herramienta nueva |
| Colores de severidad, tarjetas expandibles, retención de 2 semanas | Es presentación de la UI, no una acción sobre el sistema — el LLM ya puede transmitir la severidad usando el campo `Severity` que devuelve `get_detected_threats` |

## Resumen de la revisión completa (grupos 1–8)

Con el grupo 8 se completa la revisión de los ocho grupos de Windows Security. Estado global:

- **Implementado en la WHITELIST:** `get_defender_status`, `get_detected_threats`,
  `start_quick_scan`, `update_signatures`, `remove_all_threats`, `get_firewall_status` (ampliada
  con `AllowInboundRules`/`NotifyOnListen`), `set_firewall_profile`, `get_account_info`,
  `get_active_network_profile`, `set_block_all_incoming`, `get_allowed_firewall_rules`,
  `restore_firewall_defaults`, `start_full_scan`, `start_custom_scan`, `get_allowed_threats`,
  `get_defender_exclusions`, `get_defender_preferences` (ampliada con `PUAProtection`),
  `get_exploit_protection_status`, `get_core_isolation_status`, `get_secure_boot_status`,
  `get_tpm_status`, `get_bitlocker_status`, `get_storage_status`, `get_battery_status`,
  `get_time_service_status`.
- **Investigado y con prompt de implementación generado, pendiente de ejecutar:** ampliaciones y
  herramientas nuevas del grupo 8 (ver esa sección de este documento). Los grupos 3, 4, 5 y 6 ya
  se completaron en su totalidad (dentro de lo viable).
- **Fuera de alcance permanente y documentado:** grupo 2 (salvo `get_account_info`), grupo 7 al
  completo, y los puntos de mutación/riesgo señalados en cada grupo (Set-MpPreference, mutación
  de Exploit Protection, mutación de Core isolation/BitLocker, Restore/Allow de amenazas, entre
  otros).
- **Pendiente de una decisión explícita de Juan antes de poder implementarse:** eliminación de
  una amenaza concreta por ID (grupo 8), por el conflicto con la regla de enums cerrados.
