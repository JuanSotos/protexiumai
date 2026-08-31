"""Tests del lector del registro de auditoría (app/auditoria.py).

No se escribe ni se modifica nada del log real: la fixture `ruta_audit_temporal`
de conftest.py redirige `audit.RUTA_LOG` a un directorio temporal.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from app import auditoria, textos
from src import audit

MOMENTO = "2026-08-31T10:03:41+00:00"


def _escribir(ruta, entradas: list[dict]) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8") as f:
        for entrada in entradas:
            f.write(json.dumps(entrada, ensure_ascii=False) + "\n")


def _linea(**cambios) -> dict:
    entrada = {
        "timestamp": MOMENTO,
        "tool_id": "get_firewall_status",
        "params": {},
        "resultado": {
            "ok": True,
            "tool_id": "get_firewall_status",
            "comando": "Get-NetFirewallProfile",
            "timestamp": MOMENTO,
            "duracion_s": 0.4,
        },
        "motivo_rechazo": None,
        "proveedor": "groq",
    }
    entrada.update(cambios)
    return entrada


def test_una_lectura_correcta_se_lee_en_llano() -> None:
    entrada = auditoria.traducir(_linea())
    assert entrada.titulo == "He mirado el estado del firewall"
    assert entrada.resultado == "Hecho en 0,4 s"
    assert entrada.autor == textos.AUTOR_SIN_PERMISO
    assert entrada.proveedor == "Nube"
    assert entrada.marca == auditoria.MARCA_HECHA


@pytest.mark.parametrize("motivo", list(textos.MOTIVO_RECHAZO))
def test_cada_motivo_de_rechazo_se_traduce_a_su_frase(motivo: str) -> None:
    linea = _linea(
        tool_id="start_quick_scan",
        motivo_rechazo=motivo,
        resultado={"ok": False, "error": "rechazado", "duracion_s": 0.0, "comando": "Start-MpScan"},
    )
    entrada = auditoria.traducir(linea)
    assert entrada.resultado == textos.MOTIVO_RECHAZO[motivo]
    assert entrada.titulo == "No he analizado el equipo"
    assert not entrada.hecha


def test_el_rechazo_del_usuario_se_le_atribuye_a_el_y_el_resto_al_sistema() -> None:
    rechazo = auditoria.traducir(_linea(tool_id="start_quick_scan", motivo_rechazo="usuario_rechazo",
                                        resultado={"ok": False, "error": "cancelada", "duracion_s": 0.0}))
    elevacion = auditoria.traducir(_linea(tool_id="start_quick_scan", motivo_rechazo="requiere_admin",
                                          resultado={"ok": False, "error": "sin admin", "duracion_s": 0.0}))
    assert rechazo.autor == textos.AUTOR_RECHAZADO
    assert elevacion.autor == textos.AUTOR_SISTEMA


def test_una_accion_autorizada_y_hecha_se_le_atribuye_al_usuario() -> None:
    linea = _linea(
        tool_id="set_firewall_profile",
        params={"profile": "Public", "enabled": "True"},
        resultado={"ok": True, "duracion_s": 1.24, "comando": "Set-NetFirewallProfile"},
    )
    entrada = auditoria.traducir(linea)
    assert entrada.titulo == "He encendido el firewall en redes públicas"
    assert entrada.autor == textos.AUTOR_AUTORIZADO
    assert ("Parámetros", "perfil = Public · activar = True") in entrada.detalle


def test_el_proveedor_se_muestra_como_nube_o_local() -> None:
    assert auditoria.traducir(_linea(proveedor="groq")).proveedor == "Nube"
    assert auditoria.traducir(_linea(proveedor="ollama")).proveedor == "Local"
    assert auditoria.traducir(_linea(proveedor=None)).proveedor == "—"


@pytest.mark.parametrize(
    "mensaje,caso",
    [
        ("No se ha encontrado powershell.exe. Este equipo requiere Windows...", "powershell_no_encontrado"),
        ("El comando ha tardado más de 3600 segundos y se ha cancelado.", "timeout"),
        ("La salida de PowerShell para 'x' no es un JSON válido: ''", "salida_ilegible"),
        ("'start_full_scan' requiere privilegios de administrador.", "requiere_elevacion"),
        ("PowerShell devolvió un error al ejecutar 'x' (acceso denegado).", "error_powershell"),
        ("algo completamente distinto", None),
        (None, None),
    ],
)
def test_clasificacion_de_los_errores_del_executor(mensaje: str | None, caso: str | None) -> None:
    assert auditoria.clasificar_error(mensaje) == caso


def test_el_tiempo_agotado_se_distingue_del_resto_de_errores() -> None:
    assert auditoria.es_tiempo_agotado("El comando ha tardado más de 600 segundos y se ha cancelado.")
    assert not auditoria.es_tiempo_agotado("PowerShell devolvió un error al ejecutar 'x'.")


def test_las_dos_lineas_de_una_misma_llamada_se_funden_en_una(ruta_audit_temporal) -> None:
    """execute() registra la accion antes de ejecutarla y otra vez al terminar."""
    previa = _linea(tool_id="start_quick_scan", resultado={"ok": False, "error": auditoria.MARCA_PREVIA, "duracion_s": 0.0})
    definitiva = _linea(tool_id="start_quick_scan", resultado={"ok": True, "duracion_s": 12.0, "comando": "Start-MpScan"})
    _escribir(audit.RUTA_LOG, [previa, definitiva])

    entradas = auditoria.entradas()
    assert len(entradas) == 1
    assert entradas[0].hecha
    assert ("Registro", "se anotó antes de ejecutarse y otra vez al terminar") in entradas[0].detalle


def test_el_registro_se_puede_acotar_a_la_sesion(ruta_audit_temporal) -> None:
    vieja = _linea(timestamp="2026-08-30T09:00:00+00:00")
    nueva = _linea(timestamp="2026-08-31T11:00:00+00:00", tool_id="get_defender_status")
    _escribir(audit.RUTA_LOG, [vieja, nueva])

    desde = datetime(2026, 8, 31, 10, 0, tzinfo=timezone.utc)
    assert len(auditoria.entradas()) == 2
    assert len(auditoria.entradas(desde=desde)) == 1


def test_el_filtro_solo_sin_hacer_deja_lo_que_no_se_hizo(ruta_audit_temporal) -> None:
    hecha = _linea()
    fallida = _linea(
        timestamp="2026-08-31T10:04:00+00:00",
        tool_id="start_quick_scan",
        motivo_rechazo="usuario_rechazo",
        resultado={"ok": False, "error": "cancelada", "duracion_s": 0.0},
    )
    _escribir(audit.RUTA_LOG, [hecha, fallida])

    todas, hechas, sin_hacer = auditoria.recuento(auditoria.entradas())
    assert (todas, hechas, sin_hacer) == (2, 1, 1)
    solo = auditoria.entradas(solo_sin_hacer=True)
    assert [e.titulo for e in solo] == ["No he analizado el equipo"]


def test_un_registro_inexistente_no_rompe_la_pantalla(ruta_audit_temporal) -> None:
    assert auditoria.entradas() == []
    assert auditoria.recuento([]) == (0, 0, 0)


def test_las_lineas_corruptas_se_ignoran(ruta_audit_temporal) -> None:
    audit.RUTA_LOG.parent.mkdir(parents=True, exist_ok=True)
    with audit.RUTA_LOG.open("w", encoding="utf-8") as f:
        f.write("{esto no es json}\n")
        f.write(json.dumps(_linea(), ensure_ascii=False) + "\n")
    assert len(auditoria.entradas()) == 1


def test_la_hora_se_muestra_en_la_zona_horaria_local() -> None:
    entrada = auditoria.traducir(_linea())
    esperada = datetime.fromisoformat(MOMENTO).astimezone()
    assert entrada.hora == f"{esperada:%H:%M:%S}"
    assert entrada.hora != "--:--:--"
    # Y una marca ilegible no revienta la fila.
    assert auditoria.traducir(_linea(timestamp="no es una fecha")).hora == "--:--:--"


def test_el_desfase_horario_no_altera_el_orden(ruta_audit_temporal) -> None:
    base = datetime(2026, 8, 31, 10, 0, tzinfo=timezone.utc)
    _escribir(
        audit.RUTA_LOG,
        [
            _linea(timestamp=base.isoformat()),
            _linea(timestamp=(base + timedelta(minutes=1)).isoformat(), tool_id="get_defender_status"),
        ],
    )
    entradas = auditoria.entradas()
    assert entradas[0].titulo == "He mirado el estado de Defender"
