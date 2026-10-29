"""Worker: corre las tareas programadas del club sin que nadie tenga que lanzarlas.

Uso:  python -m app.worker

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
from app.db.session import SessionLocal
from app.services import asistencia, inscripciones

log = logging.getLogger("dragones.worker")
LATIDO = Path("/tmp/worker_latido")  # lo revisa el healthcheck de Docker
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


def tareas() -> list[Tarea]:
    s = get_settings()
    return [
        Tarea("cierre_asistencia", 7301, s.worker_cierre_segundos, _cerrar_sesiones),
        Tarea("vencer_inscripciones", 7302, s.worker_vencer_segundos, _vencer_inscripciones),
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
