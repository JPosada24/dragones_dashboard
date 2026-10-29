"""Estado de cuenta de un alumno: lo que debe al club en un solo lugar (inscripción, multas, rifas)."""
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import fechas
from app.models.alumnos import Alumno, Inscripcion
from app.models.asistencia import Multa
from app.models.dominio import ESTADOS_VIGENTES
from app.models.rifas import Rifa, Talonario
from app.services import mora


@dataclass
class DeudaRifa:
    rifa: str
    saldo: int


@dataclass
class EstadoCuenta:
    anio: int
    inscripcion_estado: str | None
    inscripcion_saldo: int
    multas_pendientes: int
    multas_saldo: int
    rifas: list[DeudaRifa] = field(default_factory=list)
    en_mora: bool = False
    entra_en_mora: date | None = None  # cuándo entra (o entró) en mora si no paga

    @property
    def total(self) -> int:
        return self.inscripcion_saldo + self.multas_saldo + sum(r.saldo for r in self.rifas)

    @property
    def al_dia(self) -> bool:
        return self.total == 0


def calcular(db: Session, alumno: Alumno) -> EstadoCuenta:
    anio = fechas.hoy().year
    inscripcion = db.scalar(select(Inscripcion).where(
        Inscripcion.alumno_id == alumno.id, Inscripcion.anio == anio, Inscripcion.estado.in_(ESTADOS_VIGENTES)
    ))
    multas = list(db.scalars(select(Multa).where(Multa.alumno_id == alumno.id, Multa.estado == "pendiente")))
    talonarios = db.scalars(
        select(Talonario).join(Talonario.rifa).where(Talonario.alumno_id == alumno.id, Rifa.estado != "cancelada")
    ).unique()
    situacion = mora.situacion(db, alumno)
    return EstadoCuenta(
        anio=anio,
        inscripcion_estado=inscripcion.estado if inscripcion else None,
        inscripcion_saldo=inscripcion.saldo if inscripcion else 0,
        multas_pendientes=len(multas),
        multas_saldo=sum(m.valor for m in multas),
        rifas=[DeudaRifa(t.rifa.nombre, t.saldo) for t in talonarios if t.saldo > 0],
        en_mora=situacion.en_mora,
        entra_en_mora=situacion.entra_en_mora,
    )
