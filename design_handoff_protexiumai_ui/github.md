repo: JuanSotos/protexiumai
branch: master

## Last sync
date: 2026-08-30T21:24:00Z

### Updated in this project
- Wireframes de la nueva interfaz (turno 2) alineados con la whitelist real de 7 herramientas y sus niveles lectura/acción/mutante.
- Los estados de propuesta, resultado y error reproducen el flujo de confirmación de `app/streamlit_app.py`.

## Screen map
| Pantalla del proyecto | Archivos del repo |
| --- | --- |
| 2a Bienvenida / 2b Conversación | app/streamlit_app.py |
| 2c / 2d Propuesta pendiente de confirmar | app/streamlit_app.py, src/executor.py (WHITELIST, niveles, requiere_admin) |
| 2e Resultado del turno | app/streamlit_app.py (_formatear_resultado), src/audit.py |
| 2f Estado del sistema en detalle | app/streamlit_app.py (_calcular_semaforo), src/executor.py |
| 2g Ajustes / proveedor | app/streamlit_app.py (PROVEEDORES, NOTA_PRIVACIDAD), src/config.py |
| 2h Error de conexión | app/streamlit_app.py (_formatear_error) |
