from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import requiere_alguno
from app.db.session import get_db
from app.models.acceso import Usuario
from app.services import resumen as servicio

router = APIRouter(prefix="/resumen", tags=["resumen"])


class IndicadoresOut(BaseModel):
    alumnos_activos: int
    inscripciones_pendientes: int
    inscripciones_vencen_pronto: int
    multas_pendientes: int
    multas_saldo: int
    alertas: int


class AlertaOut(BaseModel):
    tipo: str
    titulo: str
    detalle: str
    cuando: str
    ruta: str


class SesionHoyOut(BaseModel):
    id: str
    lugar: str | None
    horario: str
    cerrada: bool
    esperados: int
    presentes: int
    justificados: int
    ausentes: int
    sin_marcar: int


class RifaAnioOut(BaseModel):
    id: str
    nombre: str
    estado: str
    fecha_sorteo: date
    talonarios: int
    pagados: int


class CarteraOut(BaseModel):
    concepto: str
    nota: str
    monto: int


class TorneoProximoOut(BaseModel):
    id: str
    nombre: str
    rama: str
    fecha_inicio: date
    fecha_fin: date
    lugar: str | None
    ocupados: int
    cupo: int


class ResumenOut(BaseModel):
    indicadores: IndicadoresOut
    alertas: list[AlertaOut]
    hoy: list[SesionHoyOut]
    rifas: list[RifaAnioOut]
    cartera: list[CarteraOut]
    proximo_torneo: TorneoProximoOut | None


@router.get("", response_model=ResumenOut)
def ver(
    usuario: Usuario = Depends(requiere_alguno("alumnos.ver_todos", "alumnos.ver_rama")),
    db: Session = Depends(get_db),
) -> ResumenOut:
    """Tablero del staff (el Entrenador ve solo su rama). Las familias usan el estado de cuenta de cada alumno."""
    r = servicio.calcular(db, usuario)
    return ResumenOut(
        indicadores=IndicadoresOut(
            alumnos_activos=r.alumnos_activos, inscripciones_pendientes=r.inscripciones_pendientes,
            inscripciones_vencen_pronto=r.inscripciones_vencen_pronto, multas_pendientes=r.multas_pendientes,
            multas_saldo=r.multas_saldo, alertas=len(r.alertas),
        ),
        alertas=[AlertaOut(tipo=a.tipo, titulo=a.titulo, detalle=a.detalle, cuando=a.cuando, ruta=a.ruta)
                 for a in r.alertas],
        hoy=[SesionHoyOut(**{**s.__dict__, "sin_marcar": s.sin_marcar}) for s in r.hoy],
        rifas=[RifaAnioOut(**x.__dict__) for x in r.rifas],
        cartera=[CarteraOut(concepto=c, nota=n, monto=m) for c, n, m in r.cartera],
        proximo_torneo=TorneoProximoOut(**r.proximo_torneo) if r.proximo_torneo else None,
    )
