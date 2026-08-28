"""Script de demostración: comprueba que es imposible ejecutar nada fuera de la WHITELIST."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.audit import RUTA_LOG
from src.executor import execute

sys.stdout.reconfigure(encoding="utf-8")


def mostrar_resultado(titulo: str, resultado: dict) -> None:
    print(titulo)
    print("-" * len(titulo))
    if resultado["ok"]:
        print("Resultado: aceptado y ejecutado.")
        print(json.dumps(resultado["data"], indent=2, ensure_ascii=False))
    else:
        print(f"Resultado: rechazado. Motivo: {resultado['error']}")
    print()


def main() -> None:
    mostrar_resultado(
        "1) Herramienta fuera de la WHITELIST",
        execute("borrar_disco", {}),
    )

    mostrar_resultado(
        "2) Parámetro fuera del enum cerrado",
        execute("set_firewall_profile", {"profile": "Evil", "enabled": "True"}),
    )

    mostrar_resultado(
        "3) Herramienta de lectura real (sin administrador)",
        execute("get_defender_status", {}),
    )

    print("4) Últimas entradas registradas en logs/audit.jsonl")
    print("-" * 47)
    if RUTA_LOG.exists():
        lineas = RUTA_LOG.read_text(encoding="utf-8").splitlines()
        for linea in lineas[-3:]:
            entrada = json.loads(linea)
            print(
                f"- {entrada['timestamp']} | {entrada['tool_id']} | "
                f"ok={entrada['resultado']['ok']} | motivo_rechazo={entrada['motivo_rechazo']}"
            )
    else:
        print("No se ha creado el log de auditoría.")


if __name__ == "__main__":
    main()
