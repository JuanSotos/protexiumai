# Razonamiento de los mapeos a marcos de las herramientas del LLM

> **Estado: verificados por Juan Sotos el 24/10/2026** y pasados a `mapeo_marcos.csv` (columna `verificado_por`), que es la fuente que lee el catálogo. Este fichero conserva el razonamiento, los criterios y el perfil al que se dirige cada mapeo, que el CSV no puede guardar.
>
> **Origen:** las propuestas iniciales las generó la IA (Claude Code) de memoria, sin consultar las fuentes. Juan las contrastó con attack.mitre.org, el anexo II del ENS y CIS Controls v8.1, corrigió dos errores de la IA (INC-06 e INC-07 en `docs/memoria/INCIDENCIAS_IA.md`) y tomó las decisiones de criterio que constan más abajo.
>
> Solo se mapean tres marcos: CIS Controls, MITRE ATT&CK y ENS. **No hay mapeo** de CIS Benchmark (el número depende de la versión del benchmark), CCN-STIC ni D3FEND, ni de las 11 herramientas de la sección «Sin mapeo».

## Fuentes y versiones consultadas

| Marco | Versión | Dónde se contrastó |
|---|---|---|
| CIS Controls | v8.1 (marzo de 2026) | PDF en español, páginas 31 (3.6), 36 (4.4 y 4.5) y 59 (10.1 y 10.2). Es una traducción hecha con ChatGPT: para citar, usar la versión en inglés de https://www.cisecurity.org/controls |
| MITRE ATT&CK (Enterprise) | Páginas creadas el 14/04/2026 | https://attack.mitre.org/techniques/T1685/ y https://attack.mitre.org/techniques/T1686/003/ (táctica *Defense Impairment*) |
| ENS | Real Decreto 311/2022 | Anexo II: `op.exp.6`, `mp.com.1` y `mp.eq.3` |

## Criterios de Juan

1. **CIS 4.4 (cortafuegos en servidores) se conserva.** La herramienta se dividirá en un perfil Hogar y un perfil Sistemas: **4.5 va dirigida al perfil Hogar** (equipos de usuario final) y **4.4 al perfil Sistemas** (servidores). El CSV no tiene columna de perfil, así que las dos van en `cis_controls` y el perfil queda documentado aquí.
2. **ENS `mp.com.1` se conserva solo en las herramientas de cortafuegos y con encaje parcial.** La medida habla del perímetro de una red, no de un cortafuegos de equipo. Lo aprovechable para un cortafuegos de equipo es el requisito `mp.com.1.2` («todos los flujos de información a través del perímetro deben estar autorizados previamente»), equivalente a una regla de denegación por defecto. Información anotada y no mapeada: el refuerzo `op.exp.7.r3.1` cita los cambios de reglas de cortafuegos como reconfiguración dinámica ante un incidente, relacionado con `set_block_all_incoming` y `restore_firewall_defaults`.
3. **ENS en `update_signatures`: `op.exp.6`** (requisito `op.exp.6.4`: las bases de datos de detección de código dañino permanecerán permanentemente actualizadas). Se retira `op.exp.4`, que trata de parches y actualizaciones del sistema.
4. **Criterio común de ATT&CK:** la herramienta consulta o restablece el estado que la técnica intenta dañar, es decir, ayuda a detectar o contrarrestar esa técnica. Por ese criterio, `update_signatures` también lleva T1685, cuya descripción incluye impedir que las herramientas se actualicen. Las herramientas que solo informan de amenazas o lanzan análisis no llevan ATT&CK.

## Mapeos

| Herramienta (id del catálogo) | Perfil | CIS Controls v8.1 | ATT&CK | ENS | Razonamiento | Verificado |
|---|---|---|---|---|---|---|
| `get_firewall_status` | Hogar (4.5) y Sistemas (4.4) | 4.4; 4.5 | T1686.003 | mp.com.1 | Comprueba que el cortafuegos de Windows está activo; desactivarlo es la técnica T1686.003. | Sí |
| `get_allowed_firewall_rules` | Hogar (4.5) y Sistemas (4.4) | 4.4; 4.5 | T1686.003 | mp.com.1 | Revisa reglas permitidas; añadir reglas es una de las formas de la técnica. | Sí |
| `set_firewall_profile` | Hogar (4.5) y Sistemas (4.4) | 4.4; 4.5 | T1686.003 | mp.com.1 | Acción sobre los perfiles del cortafuegos (la técnica cita suprimir perfiles). | Sí |
| `set_block_all_incoming` | Hogar (4.5) y Sistemas (4.4) | 4.4; 4.5 | T1686.003 | mp.com.1 | Regla de denegación por defecto, que es lo que pide 4.5. | Sí |
| `restore_firewall_defaults` | Hogar (4.5) y Sistemas (4.4) | 4.4; 4.5 | T1686.003 | mp.com.1 | Restablece el cortafuegos tras una modificación. | Sí |
| `get_defender_status` | Hogar y Sistemas | 10.1 | T1685 | op.exp.6 | Comprueba la protección antimalware (el requisito 6.5 pide protección en tiempo real). | Sí |
| `get_defender_exclusions` | Hogar y Sistemas | 10.1 | T1685 | op.exp.6 | T1685 cita las exclusiones de Defender y su revisión con `Get-MpPreference`. | Sí |
| `get_detected_threats` | Hogar y Sistemas | 10.1 | — | op.exp.6 | Lectura de detecciones del antimalware. | Sí |
| `remove_all_threats` | Hogar y Sistemas | 10.1 | — | op.exp.6 | Respuesta a detecciones del antimalware. | Sí |
| `start_quick_scan`, `start_full_scan`, `start_custom_scan` | Hogar y Sistemas | 10.1 | — | op.exp.6 | Análisis bajo demanda (el refuerzo R1 pide escaneo periódico). | Sí |
| `update_signatures` | Hogar y Sistemas | 10.2 | T1685 | op.exp.6 | Actualización de firmas, que es el requisito 6.4 de `op.exp.6`. | Sí |
| `get_bitlocker_status` | Hogar y Sistemas | 3.6 | — | mp.eq.3 | El texto de 3.6 cita BitLocker; `mp.eq.3` incluye el cifrado de disco como refuerzo R1. | Sí |

## Sin mapeo

`get_account_info`, `get_active_network_profile`, `get_allowed_threats`, `get_defender_preferences`, `get_exploit_protection_status`, `get_core_isolation_status`, `get_secure_boot_status`, `get_tpm_status`, `get_storage_status`, `get_battery_status` y `get_time_service_status`. Quedan en `verificado: false` por defecto hasta que se les asigne un identificador contrastado.

## Alcance

Los mapeos son **orientativos**: indican con qué punto de cada marco se relaciona la herramienta, no que el equipo cumpla la norma. El ENS, por ejemplo, exige unas medidas u otras según la categoría del sistema.
