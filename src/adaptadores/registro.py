"""Adaptador del motor `registro`: lee un valor del registro de Windows en modo solo lectura (regla 11).

Solo usa `winreg.OpenKey` con `KEY_READ | KEY_WOW64_64KEY` y `winreg.QueryValueEx`; ninguna
función de escritura de `winreg` aparece en este módulo (lo comprueba `tests/test_regla1_ejecucion.py`).

Una clave o un valor inexistente no es un error del programa: es un dato. En las comprobaciones
de H2 «no existe» suele significar «Windows usa su valor por defecto», y la comprobación debe
poder distinguirlo de un fallo (`error`) o de un acceso denegado (`requiere_privilegios`). Por
eso se devuelve como éxito con `{"existe": false, "valor": null, "tipo": null}`.
"""

from __future__ import annotations

from typing import Any

from src import catalogo
from src.adaptadores.base import Invocacion, SalidaAdaptador

try:
    import winreg
except ImportError:  # fuera de Windows
    winreg = None  # type: ignore[assignment]

MOTOR = "registro"

# Mapa cerrado de los hives del catálogo a las constantes de winreg (por nombre, para que la
# política pueda comprobarlo sin importar winreg). Un hive fuera de este mapa no llega a ejecutarse.
HIVES: dict[str, str] = {
    "HKLM": "HKEY_LOCAL_MACHINE",
    "HKCU": "HKEY_CURRENT_USER",
    "HKCR": "HKEY_CLASSES_ROOT",
    "HKU": "HKEY_USERS",
    "HKCC": "HKEY_CURRENT_CONFIG",
}

# Tipos de valor de Win32 (constantes REG_* fijas del API de Windows).
_NOMBRES_TIPO: dict[int, str] = {
    1: "REG_SZ",
    2: "REG_EXPAND_SZ",
    3: "REG_BINARY",
    4: "REG_DWORD",
    7: "REG_MULTI_SZ",
    11: "REG_QWORD",
}

_NO_EXISTE: dict[str, Any] = {"existe": False, "valor": None, "tipo": None}


def construir(entrada: catalogo.Entrada, params: dict[str, str]) -> Invocacion:
    """Prepara la lectura de `clave_registro`; el motor no admite parámetros."""
    clave = entrada.clave_registro
    if clave is None:  # el cargador lo impide; se comprueba por si el catálogo se alteró en memoria
        raise ValueError(f"'{entrada.id}' no tiene clave_registro.")
    return Invocacion(
        tool_id=entrada.id,
        motor=MOTOR,
        texto=f"{clave.hive}\\{clave.ruta}\\{clave.valor}",
        timeout_s=entrada.timeout_s,
        clave=clave,
    )


def _valor_serializable(valor: Any) -> Any:
    """Convierte los valores binarios a hexadecimal para que el resultado siga siendo JSON."""
    return valor.hex() if isinstance(valor, (bytes, bytearray)) else valor


def ejecutar(invocacion: Invocacion) -> SalidaAdaptador:
    """Lee el valor y devuelve `{existe, valor, tipo}`; nunca escribe en el registro."""
    if winreg is None:
        return SalidaAdaptador(estado="no_aplicable", error="El registro de Windows no está disponible en este equipo.")
    clave = invocacion.clave
    if clave is None or clave.hive not in HIVES:
        return SalidaAdaptador(estado="error", error=f"Clave de registro no válida para '{invocacion.tool_id}'.")
    raiz = getattr(winreg, HIVES[clave.hive])
    try:
        with winreg.OpenKey(raiz, clave.ruta, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as abierta:
            valor, tipo = winreg.QueryValueEx(abierta, clave.valor)
    except FileNotFoundError:
        return SalidaAdaptador(estado="ok", datos=dict(_NO_EXISTE))
    except PermissionError:
        return SalidaAdaptador(
            estado="requiere_privilegios",
            error=f"Sin permiso para leer {invocacion.texto}. ProtexiumAI no eleva permisos automáticamente.",
        )
    except OSError as error:
        return SalidaAdaptador(estado="error", error=f"No se ha podido leer {invocacion.texto} ({error}).")
    return SalidaAdaptador(
        estado="ok",
        datos={"existe": True, "valor": _valor_serializable(valor), "tipo": _NOMBRES_TIPO.get(tipo, f"REG_{tipo}")},
    )
