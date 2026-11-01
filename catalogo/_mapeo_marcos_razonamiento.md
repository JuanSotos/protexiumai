# Razonamiento de los mapeos a marcos de las herramientas del LLM

> **Estado: verificados por Juan Sotos el 24/10/2026 (primer lote, 14 herramientas) y el 30/10/2026 (`get_exploit_protection_status`, `get_core_isolation_status`, `get_secure_boot_status` y `get_tpm_status`)** y pasados a `mapeo_marcos.csv` (columna `verificado_por`), que es la fuente que lee el catálogo. Este fichero conserva el razonamiento, los criterios y el perfil al que se dirige cada mapeo, que el CSV no puede guardar.
>
> **Origen:** las propuestas iniciales las generó la IA (Claude Code) de memoria, sin consultar las fuentes. Juan las contrastó con attack.mitre.org, el anexo II del ENS y CIS Controls v8.1, corrigió dos errores de la IA (INC-06 e INC-07 en `docs/memoria/INCIDENCIAS_IA.md`) y tomó las decisiones de criterio que constan más abajo.
>
> **Lote del 30/10/2026:** la propuesta la hizo Claude (chat) contrastando cada identificador con attack.mitre.org (ATT&CK v20) y con la especificación de evaluación de CIS Controls; Juan la verificó en esas páginas, en su PDF de CIS Controls v8.1 y en el texto consolidado del Real Decreto 311/2022, y eligió la medida del ENS.
>
> Solo se mapean tres marcos: CIS Controls, MITRE ATT&CK y ENS. **No hay mapeo** de CIS Benchmark (el número depende de la versión del benchmark), CCN-STIC ni D3FEND, ni de las 7 herramientas de la sección «Sin mapeo».

## Fuentes y versiones consultadas

| Marco | Versión | Dónde se contrastó |
|---|---|---|
| CIS Controls | v8.1 (marzo de 2026) | PDF en español, páginas 31 (3.6), 36 (4.4 y 4.5) y 59 (10.1 y 10.2); 10.5 comprobado por Juan en el mismo PDF el 30/10/2026 (usado en `get_exploit_protection_status` y `get_core_isolation_status`) y en https://controls-assessment-specification.readthedocs.io/en/latest/control-10/control-10.5.html (v8, mismo texto). Es una traducción hecha con ChatGPT: para citar, usar la versión en inglés de https://www.cisecurity.org/controls |
| MITRE ATT&CK (Enterprise) | Páginas creadas el 14/04/2026 | https://attack.mitre.org/techniques/T1685/ y https://attack.mitre.org/techniques/T1686/003/ (táctica *Defense Impairment*) |
| MITRE ATT&CK (Enterprise) | v20 (consultada el 30/10/2026) | https://attack.mitre.org/techniques/T1203/, https://attack.mitre.org/techniques/T1068/ y la mitigación https://attack.mitre.org/mitigations/M1050 (*Exploit Protection*); https://attack.mitre.org/techniques/T1003/001/, https://attack.mitre.org/techniques/T1547/008/ y la mitigación https://attack.mitre.org/mitigations/M1043 (*Credential Access Protection*, apartado «Use Credential Guard»); https://attack.mitre.org/techniques/T1542/001/, https://attack.mitre.org/techniques/T1542/003/ y la mitigación https://attack.mitre.org/mitigations/M1046 (*Boot Integrity*, apartados «Implementation of Secure Boot» y «Utilization of TPMs») |
| ENS | Real Decreto 311/2022 | Anexo II: `op.exp.6`, `mp.com.1` y `mp.eq.3`; el 30/10/2026, `op.exp.6.1`, `op.exp.6.r2.1` y `op.exp.2` en el texto consolidado del BOE (páginas 44 y 41) |

## Criterios de Juan

1. **CIS 4.4 (cortafuegos en servidores) se conserva.** La herramienta se dividirá en un perfil Hogar y un perfil Sistemas: **4.5 va dirigida al perfil Hogar** (equipos de usuario final) y **4.4 al perfil Sistemas** (servidores). El CSV no tiene columna de perfil, así que las dos van en `cis_controls` y el perfil queda documentado aquí.
2. **ENS `mp.com.1` se conserva solo en las herramientas de cortafuegos y con encaje parcial.** La medida habla del perímetro de una red, no de un cortafuegos de equipo. Lo aprovechable para un cortafuegos de equipo es el requisito `mp.com.1.2` («todos los flujos de información a través del perímetro deben estar autorizados previamente»), equivalente a una regla de denegación por defecto. Información anotada y no mapeada: el refuerzo `op.exp.7.r3.1` cita los cambios de reglas de cortafuegos como reconfiguración dinámica ante un incidente, relacionado con `set_block_all_incoming` y `restore_firewall_defaults`.
3. **ENS en `update_signatures`: `op.exp.6`** (requisito `op.exp.6.4`: las bases de datos de detección de código dañino permanecerán permanentemente actualizadas). Se retira `op.exp.4`, que trata de parches y actualizaciones del sistema.
4. **Criterio común de ATT&CK:** la herramienta consulta o restablece el estado que la técnica intenta dañar, es decir, ayuda a detectar o contrarrestar esa técnica. Por ese criterio, `update_signatures` también lleva T1685, cuya descripción incluye impedir que las herramientas se actualicen. Las herramientas que solo informan de amenazas o lanzan análisis no llevan ATT&CK.
5. **Criterio de ATT&CK por mitigación (aceptado el 30/10/2026):** una herramienta también lleva una técnica si comprueba que está activa la mitigación oficial de MITRE para esa técnica; la mitigación se cita en el razonamiento, no en el CSV. Primer caso: `get_exploit_protection_status` → M1050 (*Exploit Protection*), que cubre T1203 y T1068.
6. **ENS en `get_exploit_protection_status`: `op.exp.6`** (requisito `op.exp.6.1`: «se dispondrá de mecanismos de prevención y reacción frente a código dañino»). DEP, ASLR y CFG son mecanismos de prevención frente a la ejecución de código dañino. Se descarta `op.exp.2` («Configuración de seguridad»), que trata de la configuración antes de la entrada en operación y solo encajaría de forma genérica con `op.exp.2.3` («seguridad por defecto»).
7. **`get_core_isolation_status`:** ATT&CK por M1043, cuyo apartado «Use Credential Guard» aísla la memoria de LSASS (T1003.001) y ejecuta lsass.exe en un entorno virtualizado aislado (T1547.008). Se descarta T1068: su página no menciona HVCI ni la integridad de memoria y ninguna de sus mitigaciones es lo que consulta la herramienta. CIS 10.5 cubre la parte de integridad de memoria (HVCI), no Credential Guard. ENS `op.exp.6` (requisito `op.exp.6.1`) por la misma parte; las medidas de credenciales del ENS (`op.acc.5`, `op.acc.6`) tratan de su ciclo de vida, no de proteger la memoria, y no se usan.
8. **`get_secure_boot_status` y `get_tpm_status`:** ATT&CK por M1046 (*Boot Integrity*). Secure Boot impide que arranque un cargador no firmado (apartado «Implementation of Secure Boot»): T1542.003 (*Bootkit*); no lleva T1542.001 porque Secure Boot no verifica el firmware. La atestación con TPM detecta cambios en el firmware y en el cargador (apartado «Utilization of TPMs»): T1542.001 y T1542.003. Sin CIS Controls: 4.1 trata de documentar un proceso de configuración segura, no de una función concreta. ENS `op.exp.6` por su **refuerzo R2, «Revisión preventiva del sistema»** (`op.exp.6.r2.1`: «las funciones críticas se analizarán al arrancar el sistema en prevención de modificaciones no autorizadas»); el CSV no tiene columna de refuerzo, por eso consta aquí, como `mp.com.1.2` en el criterio 2. El refuerzo R2 solo es exigible a partir de la categoría MEDIA.

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
| `get_exploit_protection_status` | Hogar y Sistemas | 10.5 | T1203; T1068 | op.exp.6 | 10.5 cita DEP y Windows Defender Exploit Guard; la mitigación M1050 (DEP, ASLR, CFG) cubre T1203 y T1068 (criterio 5); `op.exp.6.1` pide mecanismos de prevención frente a código dañino (criterio 6). | Sí (30/10/2026) |
| `get_core_isolation_status` | Hogar y Sistemas | 10.5 | T1003.001; T1547.008 | op.exp.6 | Consulta Credential Guard e integridad de memoria (HVCI); ver criterio 7. | Sí (30/10/2026) |
| `get_secure_boot_status` | Hogar y Sistemas | — | T1542.003 | op.exp.6 (R2: op.exp.6.r2.1) | Secure Boot impide arrancar un cargador no firmado (bootkit); ver criterio 8. | Sí (30/10/2026) |
| `get_tpm_status` | Hogar y Sistemas | — | T1542.001; T1542.003 | op.exp.6 (R2: op.exp.6.r2.1) | La atestación con TPM detecta cambios en firmware y cargador; ver criterio 8. | Sí (30/10/2026) |

## Sin mapeo

`get_account_info`, `get_active_network_profile`, `get_allowed_threats`, `get_defender_preferences`, `get_storage_status`, `get_battery_status` y `get_time_service_status`. Quedan en `verificado: false` por defecto hasta que se les asigne un identificador contrastado.

## Alcance

Los mapeos son **orientativos**: indican con qué punto de cada marco se relaciona la herramienta, no que el equipo cumpla la norma. El ENS, por ejemplo, exige unas medidas u otras según la categoría del sistema.
