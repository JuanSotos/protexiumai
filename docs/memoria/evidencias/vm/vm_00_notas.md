# Notas de la prueba en máquina virtual

- Fechas: 24 y 25 de octubre de 2026
- Windows: Microsoft Windows 11 Home, versión 10.0.26300 (compilación 26300; de `vm_00_windows.txt`)
- Hipervisor: VirtualBox
- Instantánea de partida: Base limpia
- Python: 3.13 (entorno virtual propio)
- Proveedor LLM: Groq (openai/gpt-oss-20b)
- Código probado: último commit tras corregir INC-08, INC-09 e INC-10

## Resultados

| Prueba | Resultado |
|---|---|
| Instalación desde cero siguiendo el README | Correcta, con las observaciones 1 y 2 |
| Tests (`python -m pytest`) | 458 passed (tras corregir INC-09 e INC-10) |
| Detección de plataforma (`python -m src.plataforma`) Correcta: Windows 11, compilación 26300, sin elevar (`vm_02_plataforma.json`) |
| Escenario 1 (diagnóstico) Consultó Defender, cortafuegos y otras 5 herramientas de lectura sin pedir confirmación; con errores de interpretación del modelo (puntos 11 y 13) |
| Escenario 2 (alerta EICAR) | Respondió sin error tras corregir INC-08 (6 detecciones en el historial); el modelo dijo erróneamente que las firmas estaban al día (punto 13) |
| Escenario 3, cancelar | Correcto: no se ejecuta nada y queda auditado (`usuario_rechazo`) |
| Escenario 3, confirmar | Correcto: Private pasa a activado y la verificación lo confirma |
| Tildes en las salidas de PowerShell | Correctas tras corregir INC-10 |

## Incidencias y observaciones

1. En una terminal elevada nueva hay que activar el entorno virtual antes de usar `python`; sin activarlo, `No module named pytest`.
2. Al principio, con `(venv)` en el prompt, `python` apuntaba al de la Tienda de Windows. Solución: borrar y recrear el entorno. Causa no determinada.
3. `Set-NetFirewallProfile` dio «Acceso denegado» en una terminal sin privilegios de administrador. Solución: abrir la terminal como administrador.
4. Error 413 de Groq (límite de 8.000 tokens por minuto del plan gratuito): peticiones de 12.237 y 10.446 tokens. Con 6 detecciones, `get_detected_threats` devolvía 72.687 caracteres. Corregido recortando la salida que se envía al LLM (INC-08).
5. `pytest` en la VM: 1 fallo porque el equipo se llama `windows11`, que coincide con la clave `es_windows11` del JSON de plataforma. No había fuga de datos. Corregido con nombres ficticios en el test (INC-09).
6. El navegador bloqueó la descarga del fichero EICAR; se generó desde PowerShell con la cadena estándar. Defender lo detectó y lo puso en cuarentena.
7. Escenario 3: con la frase del guion («revisa mi firewall») el modelo no propuso la acción; hizo falta pedirla («sí, activa el perfil Privado»).
8. Captura `vm_04_firewall_antes_normal.png`: estado original del cortafuegos (Private activado), antes de desactivarlo para preparar el Escenario 3.
9. La salida de PowerShell con tildes llegaba corrupta al LLM y a la auditoría (página OEM leída como ANSI). Corregido en el ejecutor (INC-10).
10. El log de auditoría contiene el usuario y el nombre del equipo reales (`get_account_info`). Por eso `logs/` no se versiona y la evidencia se extrajo sin esos datos.
11. El modelo inventó el significado de valores numéricos en bruto (campo `Profile` de las reglas, categoría de red «Privada (valor 0)», `AllowInboundRules=2` como «permitidas») y citó reglas RDP y SMB que no estaban en los datos. No se corrige; queda como limitación conocida (INC-11).
12. El modelo envió un parámetro no declarado a `get_allowed_firewall_rules`; el ejecutor lo rechazó (`parametro_no_declarado`), quedó auditado y el reintento salió bien.
13. El modelo no sabe leer las fechas `/Date(ms)/` de PowerShell: dijo que las firmas de Defender estaban actualizadas («5 oct. 2026», «fecha de hoy») cuando la barra lateral mostraba «hace 402 días» (17/09/2025). Se aprecia en `vm_06` y `vm_08`. No se corrige; limitación conocida (INC-12).
14. La captura `vm_08_escenario2_respuesta.png` se corta antes de la conclusión sobre el fichero EICAR; el resultado de la consulta de amenazas sí consta en el log de auditoría (`get_detected_threats`). En los títulos de la interfaz (`vm_10`, `vm_12`) los asteriscos de Markdown salen sin interpretar; es un defecto menor de la vista.

## Ficheros de esta prueba

- `vm_00_windows.txt`, `vm_01_pytest.txt`, `vm_02_plataforma.json`
- `vm_03_audit_resumen.txt`, `vm_03_audit_set_firewall.txt`
- Capturas `vm_02` a `vm_16`