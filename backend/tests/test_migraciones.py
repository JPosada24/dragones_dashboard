"""Migraciones que transforman datos: se prueban en una base aparte con datos de la versión anterior."""
import os
import uuid
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from alembic import command

INI = str(Path(__file__).resolve().parents[1] / "alembic.ini")


@pytest.fixture
def base_aparte():
    url = make_url(os.environ["DATABASE_URL"])
    nombre = f"{url.database}_migracion"
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{nombre}"'))
        c.execute(text(f'CREATE DATABASE "{nombre}"'))
    motor = create_engine(url.set(database=nombre))
    yield motor
    motor.dispose()
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{nombre}"'))
    admin.dispose()


def _migrar(conn, version):
    cfg = Config(INI)
    cfg.attributes["connection"] = conn
    command.upgrade(cfg, version)


def test_0012_pasa_los_pagos_de_puestos_al_talonario_y_las_actas_a_boletas(base_aparte):
    alumno, rifa, talonario, acta = (uuid.uuid4() for _ in range(4))
    puestos = [uuid.uuid4() for _ in range(20)]
    with base_aparte.begin() as conn:
        _migrar(conn, "0011")
        conn.execute(text(
            "INSERT INTO alumnos (id, codigo, nombres, apellidos, tipo_documento, documento_cifrado, documento_indice,"
            " documento_ultimos, fecha_nacimiento, rama) VALUES (:id, 'F007', 'Laura', 'Pérez', 'CC', 'x', 'i', '1234',"
            " '2000-01-01', 'femenina')"
        ), {"id": alumno})
        conn.execute(text(
            "INSERT INTO rifas (id, nombre, anio, numero, premio, fecha_sorteo, puestos_por_talonario, precio_puesto,"
            " estado) VALUES (:id, 'Rifa 1', 2026, 1, 'Balón', '2026-11-12', 20, 2000, 'sorteada')"
        ), {"id": rifa})
        conn.execute(text("INSERT INTO talonarios (id, rifa_id, alumno_id, indice, codigo)"
                          " VALUES (:id, :r, :a, 1, 'F007')"), {"id": talonario, "r": rifa, "a": alumno})
        for k, p in enumerate(puestos):  # segundo talonario de la rifa: puestos 20 a 39
            conn.execute(text("INSERT INTO puestos (id, rifa_id, talonario_id, numero, monto_pagado)"
                              " VALUES (:id, :r, :t, :n, 2000)"), {"id": p, "r": rifa, "t": talonario, "n": 20 + k})
            conn.execute(text("INSERT INTO pagos_puesto (id, puesto_id, fecha, monto)"
                              " VALUES (:id, :p, '2026-11-02', 2000)"), {"id": uuid.uuid4(), "p": p})
        errado = uuid.uuid4()
        conn.execute(text("INSERT INTO pagos_puesto (id, puesto_id, fecha, monto) VALUES (:id, :p, '2026-11-02', 500)"),
                     {"id": errado, "p": puestos[0]})
        conn.execute(text("INSERT INTO pagos_puesto (id, puesto_id, fecha, monto, anula_id, motivo)"
                          " VALUES (:id, :p, '2026-11-03', -500, :a, 'Error')"),
                     {"id": uuid.uuid4(), "p": puestos[0], "a": errado})
        conn.execute(text(
            "INSERT INTO actas_sorteo (id, rifa_id, numero_ganador, puesto_id, alumno_id, comprador_nombre,"
            " participantes, total_participantes, huella)"
            " VALUES (:id, :r, 26, :p, :a, 'Doña Rosa', CAST(:lista AS jsonb), 20, 'h')"
        ), {"id": acta, "r": rifa, "p": puestos[6], "a": alumno, "lista": str(list(range(20, 40)))})

        _migrar(conn, "0012")

        pagos = conn.execute(text("SELECT monto, anula_id IS NOT NULL FROM pagos_talonario WHERE talonario_id = :t"),
                             {"t": talonario}).all()
        assert len(pagos) == 22 and sum(m for m, _ in pagos) == 40000 and sum(a for _, a in pagos) == 1
        a = conn.execute(text(
            "SELECT orden, codigo, boleta, talonario_id, participantes, huella FROM actas_sorteo"
        )).one()
        assert (a.orden, a.codigo, a.boleta, a.talonario_id) == (1, "F007", 7, talonario)
        assert a.participantes == [f"F007-{n:02d}" for n in range(1, 21)] and a.huella == "h"
        for tabla in ("puestos", "pagos_puesto"):
            assert conn.execute(text("SELECT to_regclass(:t)"), {"t": tabla}).scalar() is None
