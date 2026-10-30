"""Worker: corre las tareas programadas del club sin que nadie tenga que lanzarlas.

Uso:  python -m app.worker

Tareas: cierre diario de asistencia, vencimiento de inscripciones, mora, avisos programados y envío de correos.

Cada tarea es idempotente (repetirla no duplica nada), así que el worker solo la ejecuta cada cierto
intervalo: si estuvo apagado, al volver se pone al día. Un "advisory lock" de PostgreSQL impide que dos
workers ejecuten la misma tarea a la vez.
"""
import logging
import signal
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.core import fechas
from app.core.config import get_settings
from app.core.correo import get_correo
from app.db.session import SessionLocal
from app.services import asistencia, inscripciones, mora, notificaciones, programacion

log = logging.getLogger("dragones.worker")
LATIDO = Path("/tmp/worker_latido")  # noqa: S108  (solo dentro del contenedor; lo revisa el healthcheck)
PAUSA_SEGUNDOS = 15


@dataclass
class Tarea:
    nombre: str
    bloqueo: int  # clave del advisory lock de PostgreSQL
    cada_segundos: int
    funcion: Callable[[Session], str | None]  # devuelve un resumen, o None si no hubo nada que hacer
    proxima: float = 0.0


def _cerrar_sesiones(db: Session) -> str | None:
    r = asistencia.cerrar(db, ahora=fechas.ahora())
    if not r.sesiones:
        return None
    return f"{r.sesiones} sesiones cerradas, {r.ausencias} ausencias, {r.multas} multas"


def _vencer_inscripciones(db: Session) -> str | None:
    n = inscripciones.vencer(db, en=fechas.hoy())
    return f"{n} inscripciones vencidas" if n else None


def _avisos_programados(db: Session) -> str | None:
    recordatorios = notificaciones.recordatorios_inscripcion(db)
    alertas = notificaciones.alertas_inasistencia(db)
    if not (recordatorios or alertas):
        return None
    return f"{recordatorios} recordatorios de pago, {alertas} alertas de inasistencia"


def _enviar_correos(db: Session) -> str | None:
    enviados, fallidos = notificaciones.enviar_correos(db, get_correo(), ahora=fechas.ahora())
    if not (enviados or fallidos):
        return None
    return f"{enviados} correos enviados, {fallidos} fallidos definitivamente"


def _programar_sesiones(db: Session) -> str | None:
    r = programacion.generar(db)
    if not r.hubo_cambios:
        return None
    return f"{r.creadas} sesiones creadas, {r.canceladas} canceladas, {r.reactivadas} reactivadas"


def _revisar_mora(db: Session) -> str | None:
    r = mora.revisar(db)
    if not (r.a_expulsar or r.expulsados or r.al_dia or r.avisos):
        return None
    return f"{r.a_expulsar} a expulsar, {r.expulsados} expulsados, {r.al_dia} al día, {r.avisos} avisos de mora"


def tareas() -> list[Tarea]:
    s = get_settings()
    return [
        Tarea("cierre_asistencia", 7301, s.worker_cierre_segundos, _cerrar_sesiones),
        Tarea("vencer_inscripciones", 7302, s.worker_vencer_segundos, _vencer_inscripciones),
        Tarea("mora", 7305, s.worker_mora_segundos, _revisar_mora),
        Tarea("programar_sesiones", 7306, s.worker_programacion_segundos, _programar_sesiones),
        Tarea("avisos_programados", 7303, s.worker_notificaciones_segundos, _avisos_programados),
        Tarea("enviar_correos", 7304, s.worker_correos_segundos, _enviar_correos),
    ]


class Omitida(Exception):
    """Otro worker tiene la tarea en curso."""


def ejecutar(tarea: Tarea, fabrica: sessionmaker = SessionLocal) -> str | None:
    """Corre una tarea en su propia transacción. El lock es de transacción: se libera solo al terminar."""
    with fabrica() as db:
        if not db.scalar(text("SELECT pg_try_advisory_xact_lock(:clave)"), {"clave": tarea.bloqueo}):
            raise Omitida
        resultado = tarea.funcion(db)
        db.commit()
        return resultado


def ciclo(lista: list[Tarea], ahora: float) -> None:
    for tarea in lista:
        if ahora < tarea.proxima:
            continue
        tarea.proxima = ahora + tarea.cada_segundos
        try:
            resultado = ejecutar(tarea)
        except Omitida:
            log.info("%s: omitida, otro worker la está ejecutando", tarea.nombre)
        except Exception:
            # Un fallo (p. ej. la base reiniciándose) no tumba el worker: se reintenta en el próximo turno.
            log.exception("%s falló; se reintenta en %s s", tarea.nombre, tarea.cada_segundos)
        else:
            if resultado:
                log.info("%s: %s", tarea.nombre, resultado)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parar = threading.Event()
    for senal in (signal.SIGTERM, signal.SIGINT):
        signal.signal(senal, lambda *_: parar.set())  # docker stop: termina el ciclo actual y sale limpio

    lista = tareas()
    log.info("Worker iniciado: %s", ", ".join(f"{t.nombre} cada {t.cada_segundos} s" for t in lista))
    while not parar.is_set():
        ciclo(lista, time.monotonic())
        LATIDO.write_text(str(int(time.time())))
        parar.wait(PAUSA_SEGUNDOS)
    log.info("Worker detenido.")


if __name__ == "__main__":
    main()
