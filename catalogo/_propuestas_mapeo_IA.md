# Propuestas de mapeo a marcos — PROPUESTA IA — SIN VERIFICAR

> **Estado: `verificado: false`.** Estas propuestas las ha escrito la IA **de memoria, sin consultar las fuentes oficiales**, y pueden contener errores. No están en `mapeo_marcos.csv` ni se leen desde el catálogo (regla 15 de `CLAUDE.md`). Para que un mapeo valga, Juan debe comprobar cada identificador en su fuente y copiarlo a `catalogo/mapeo_marcos.csv` rellenando `verificado_por` y `fecha`.
>
> Solo se proponen tres marcos de los que la IA recuerda con razonable seguridad: CIS Controls v8, MITRE ATT&CK y ENS. **No se proponen** CIS Benchmark (el número de recomendación depende de la versión del benchmark), CCN-STIC ni D3FEND, porque la IA no puede recordarlos con fiabilidad. Las herramientas que no aparecen aquí tampoco tienen propuesta.

## Fuentes donde verificar

- CIS Controls v8: https://www.cisecurity.org/controls (salvaguardas 4.4, 4.5, 10.1, 10.2, 3.6)
- MITRE ATT&CK (Enterprise): https://attack.mitre.org (técnicas T1562.001 y T1562.004)
- ENS (Real Decreto 311/2022): medidas del anexo II (`op.exp.4`, `op.exp.6`, `mp.com.1`, `mp.info.3`)

## Propuestas

| Herramienta (id del catálogo) | CIS Controls v8 | ATT&CK | ENS | Razonamiento de la IA | Verificado |
|---|---|---|---|---|---|
| `get_firewall_status` | 4.4; 4.5 | T1562.004 | mp.com.1 | Cortafuegos activo en el equipo; desactivarlo es una técnica de evasión de defensas. | No |
| `get_allowed_firewall_rules` | 4.4; 4.5 | T1562.004 | mp.com.1 | Revisión de las reglas de entrada permitidas. | No |
| `set_firewall_profile` | 4.4; 4.5 | T1562.004 | mp.com.1 | Acción sobre el cortafuegos; la técnica ATT&CK es la de desactivarlo. | No |
| `set_block_all_incoming` | 4.4; 4.5 | T1562.004 | mp.com.1 | Endurece el cortafuegos bloqueando entradas. | No |
| `restore_firewall_defaults` | 4.4; 4.5 | T1562.004 | mp.com.1 | Restaura el cortafuegos a su configuración de fábrica. | No |
| `get_defender_status` | 10.1 | T1562.001 | op.exp.6 | Protección antimalware activa; desactivarla es una técnica de evasión. | No |
| `get_defender_exclusions` | 10.1 | T1562.001 | op.exp.6 | Las exclusiones son una vía habitual para ocultar malware al antivirus. | No |
| `get_detected_threats` | 10.1 | — | op.exp.6 | Lectura de detecciones del antimalware. | No |
| `remove_all_threats` | 10.1 | — | op.exp.6 | Respuesta a detecciones del antimalware. | No |
| `start_quick_scan`, `start_full_scan`, `start_custom_scan` | 10.1 | — | op.exp.6 | Análisis bajo demanda con antimalware. | No |
| `update_signatures` | 10.2 | — | op.exp.6; op.exp.4 | Actualización de firmas del antimalware. | No |
| `get_bitlocker_status` | 3.6 | — | mp.info.3 | Cifrado de datos en dispositivos de usuario. | No |

## Sin propuesta

`get_account_info`, `get_active_network_profile`, `get_allowed_threats`, `get_defender_preferences`, `get_exploit_protection_status`, `get_core_isolation_status`, `get_secure_boot_status`, `get_tpm_status`, `get_storage_status`, `get_battery_status` y `get_time_service_status`: la IA no tiene un identificador del que se fíe lo suficiente.

## Cómo pasar una propuesta verificada al CSV

1. Comprueba cada identificador en la fuente oficial y corrige lo que no coincida.
2. Añade una fila a `catalogo/mapeo_marcos.csv` con la cabecera exacta `id,cis_benchmark,cis_id,cis_titulo_breve,cis_controls,ccn,attack,d3fend,ens,verificado_por,fecha`, listas separadas por `;` y la fecha como `AAAA-MM-DD`.
3. Rellena `verificado_por` con tu nombre. Sin él, el cargador deja el mapeo como `verificado: false`.
4. Ejecuta `python -m pytest tests/test_catalogo.py`.
