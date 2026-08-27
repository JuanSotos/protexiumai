"""Script de verificación de la ejecución de comandos PowerShell desde Python."""

import json
import re
import subprocess
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

COMANDO = [
    "powershell.exe",
    "-NoProfile",
    "-NonInteractive",
    "-Command",
    "Get-MpComputerStatus | Select-Object AMServiceEnabled, RealTimeProtectionEnabled, "
    "AntivirusSignatureLastUpdated, QuickScanEndTime | ConvertTo-Json",
]

ETIQUETAS = {
    "AMServiceEnabled": "Servicio de Windows Defender activo",
    "RealTimeProtectionEnabled": "Protección en tiempo real",
    "AntivirusSignatureLastUpdated": "Última actualización de firmas",
    "QuickScanEndTime": "Última exploración rápida",
}


PATRON_FECHA_DOTNET = re.compile(r"^/Date\((\d+)\)/$")


def formatear_valor(valor: object) -> str:
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    if valor is None:
        return "No disponible"
    if isinstance(valor, str):
        coincidencia = PATRON_FECHA_DOTNET.match(valor)
        if coincidencia:
            timestamp_ms = int(coincidencia.group(1))
            fecha = datetime.fromtimestamp(timestamp_ms / 1000)
            return fecha.strftime("%d/%m/%Y %H:%M:%S")
    return str(valor)


def main() -> None:
    try:
        resultado = subprocess.run(
            COMANDO,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        print(
            "Error: no se ha encontrado powershell.exe. "
            "Este script requiere Windows con PowerShell disponible en el PATH.",
            file=sys.stderr,
        )
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print(
            "Error: el comando de PowerShell ha tardado más de 30 segundos y se ha cancelado.",
            file=sys.stderr,
        )
        sys.exit(1)

    if resultado.returncode != 0:
        error_ps = resultado.stderr.strip() or "sin detalles adicionales"
        print(
            f"Error: PowerShell devolvió un error al ejecutar el comando ({error_ps}).",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        datos = json.loads(resultado.stdout)
    except json.JSONDecodeError:
        print(
            "Error: la salida de PowerShell no es un JSON válido. Salida recibida:\n"
            f"{resultado.stdout.strip()}",
            file=sys.stderr,
        )
        sys.exit(1)

    print("Estado de Windows Defender")
    print("---------------------------")
    for clave, etiqueta in ETIQUETAS.items():
        print(f"{etiqueta}: {formatear_valor(datos.get(clave))}")


if __name__ == "__main__":
    main()
