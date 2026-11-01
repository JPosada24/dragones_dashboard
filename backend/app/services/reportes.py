"""Reportes de dinero: ingresos por mes y concepto, y exportación de movimientos a CSV.

Se suman los movimientos tal cual quedaron registrados: una anulación es un movimiento negativo en la fecha en que se
anuló, así el total de cada mes es el dinero que de verdad entró ese mes. El dinero de rifas y torneos eliminados
sigue contando (se conservan sus pagos).
"""
import csv
import io
from datetime import date
from typing import Any

from sqlalchemy import String, cast, extract, func, literal, select, union_all
from sqlalchemy.orm import Session

from app.models.alumnos import Alumno, Inscripcion, PagoInscripcion
from app.models.asistencia import Multa
from app.models.rifas import PagoTalonario, Rifa, Talonario
from app.models.torneos import EquipoTorneo, PagoEquipo, Torneo

CONCEPTOS = ("inscripciones", "multas", "rifas", "torneos")


def _movimientos():
    """Todos los movimientos de dinero en una sola consulta: fecha, concepto, referencia, detalle y monto."""
    alumno = Alumno.codigo + literal(" · ") + Alumno.nombres + literal(" ") + Alumno.apellidos
    return union_all(
        select(PagoInscripcion.fecha.label("fecha"), literal("inscripciones").label("concepto"),
               alumno.label("referencia"), (literal("Inscripción ") + cast(Inscripcion.anio, String)).label("detalle"),
               PagoInscripcion.monto.label("monto"))
        .join(Inscripcion, Inscripcion.id == PagoInscripcion.inscripcion_id)
        .join(Alumno, Alumno.id == Inscripcion.alumno_id),
        select(Multa.fecha_pago, literal("multas"), alumno, literal("Multa por inasistencia"), Multa.valor)
        .join(Alumno, Alumno.id == Multa.alumno_id).where(Multa.estado == "pagada"),
        select(PagoTalonario.fecha, literal("rifas"), alumno, Rifa.nombre, PagoTalonario.monto)
        .join(Talonario, Talonario.id == PagoTalonario.talonario_id).join(Rifa, Rifa.id == Talonario.rifa_id)
        .join(Alumno, Alumno.id == Talonario.alumno_id),
        select(PagoEquipo.fecha, literal("torneos"), EquipoTorneo.nombre_club, Torneo.nombre, PagoEquipo.monto)
        .join(EquipoTorneo, EquipoTorneo.id == PagoEquipo.equipo_id).join(Torneo, Torneo.id == EquipoTorneo.torneo_id),
    ).subquery()


def ingresos(db: Session, anio: int) -> list[dict[str, Any]]:
    """Doce filas (una por mes) con el neto de cada concepto y el total."""
    m = _movimientos()
    filas = db.execute(
        select(extract("month", m.c.fecha).label("mes"), m.c.concepto, func.sum(m.c.monto))
        .where(extract("year", m.c.fecha) == anio).group_by("mes", m.c.concepto)
    ).all()
    meses = [{"mes": n, **dict.fromkeys(CONCEPTOS, 0), "total": 0} for n in range(1, 13)]
    for mes, concepto, total in filas:
        meses[int(mes) - 1][concepto] = int(total)
        meses[int(mes) - 1]["total"] += int(total)
    return meses


def _celda(valor: Any) -> Any:
    """Evita la inyección de fórmulas al abrir el CSV en Excel (texto que empieza por = + - @)."""
    if isinstance(valor, str) and valor[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + valor
    return valor


def movimientos_csv(db: Session, desde: date, hasta: date) -> str:
    m = _movimientos()
    filas = db.execute(
        select(m.c.fecha, m.c.concepto, m.c.referencia, m.c.detalle, m.c.monto)
        .where(m.c.fecha.between(desde, hasta)).order_by(m.c.fecha, m.c.concepto)
    ).all()
    salida = io.StringIO()
    escritor = csv.writer(salida, delimiter=";")  # ";" para que Excel en español separe las columnas
    escritor.writerow(["fecha", "concepto", "referencia", "detalle", "monto"])
    for fila in filas:
        escritor.writerow([fila.fecha.isoformat(), fila.concepto, *(_celda(v) for v in fila[2:4]), fila.monto])
    return "﻿" + salida.getvalue()  # BOM: Excel reconoce las tildes
