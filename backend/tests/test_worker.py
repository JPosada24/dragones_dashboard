from datetime import timedelta

import pytest
from sqlalchemy import text

from app import worker
from app.db.session import engine
from tests.fabrica import LUNES, I, M, alumno_inscrito, crear_sesion, en_hora


def _tarea(nombre: str) -> worker.Tarea:
    return next(t for t in worker.tareas() if t.nombre == nombre)


def test_el_worker_cierra_la_asistencia_y_genera_multas(client, h_admin, reloj):
    alumno_inscrito(client, h_admin)
    crear_sesion(client, h_admin)
    tarea = _tarea("cierre_asistencia")
    assert worker.ejecutar(tarea) is None  # a las 10:00 aún no hay nada que cerrar

    reloj(en_hora(LUNES, 23, 59))
    assert worker.ejecutar(tarea) == "1 sesiones cerradas, 1 ausencias, 1 multas"
    assert worker.ejecutar(tarea) is None  # idempotente
    assert len(client.get(M, headers=h_admin).json()) == 1


def test_el_worker_vence_inscripciones_sin_pagar(client, h_admin, reloj):
    alumna = alumno_inscrito(client, h_admin, documento="2000000005")
    tarea = _tarea("vencer_inscripciones")
    reloj(en_hora(LUNES + timedelta(days=30), 9))  # último día del plazo: aún no vence
    assert worker.ejecutar(tarea) is None
    reloj(en_hora(LUNES + timedelta(days=31), 9))
    assert worker.ejecutar(tarea) == "1 inscripciones vencidas"
    i = client.get(I, params={"alumno_id": alumna["id"]}, headers=h_admin).json()[0]
    assert i["estado"] == "rechazado" and i["causa_rechazo"] == "vencimiento"


def test_dos_workers_no_corren_la_misma_tarea_a_la_vez():
    tarea = _tarea("cierre_asistencia")
    with engine.connect() as otro_worker:
        otro_worker.execute(text("SELECT pg_advisory_lock(:k)"), {"k": tarea.bloqueo})
        try:
            with pytest.raises(worker.Omitida):
                worker.ejecutar(tarea)
        finally:
            otro_worker.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": tarea.bloqueo})
    assert worker.ejecutar(tarea) is None  # liberado el lock, corre normalmente


def test_un_fallo_en_una_tarea_no_detiene_las_demas(caplog):
    llamadas = []

    def rota(db):
        raise RuntimeError("base reiniciándose")

    def sana(db):
        llamadas.append(1)
        return "ok"

    lista = [worker.Tarea("rota", 9001, 60, rota), worker.Tarea("sana", 9002, 60, sana)]
    worker.ciclo(lista, ahora=1000.0)
    assert llamadas == [1] and "rota falló" in caplog.text
    worker.ciclo(lista, ahora=1030.0)  # aún no toca de nuevo
    assert llamadas == [1]
    worker.ciclo(lista, ahora=1061.0)
    assert llamadas == [1, 1]

