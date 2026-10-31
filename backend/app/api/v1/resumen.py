from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import requiere
from app.db.session import get_db
from app.models.acceso import Usuario
from app.schemas.resumen import (
    AlertaResumenOut,
    CarteraOut,
    IndicadoresOut,
    ResumenOut,
    RifaAnioOut,
    SesionHoyOut,
    TorneoProximoOut,
)
from app.services import resumen as servicio

router = APIRouter(prefix="/resumen", tags=["resumen"])


@router.get("", response_model=ResumenOut)
def ver(
    usuario: Usuario = Depends(requiere("alumnos.ver_todos")),
    db: Session = Depends(get_db),
) -> ResumenOut:
    """Tablero del staff (el Entrenador ve solo su rama). Las familias usan el estado de cuenta de cada alumno."""
    r = servicio.calcular(db, usuario)
    return ResumenOut(
        indicadores=IndicadoresOut(
            alumnos_activos=r.alumnos_activos, alumnos_sin_inscripcion=r.alumnos_sin_inscripcion,
            inscripciones_pendientes=r.inscripciones_pendientes,
            inscripciones_vencen_pronto=r.inscripciones_vencen_pronto, multas_pendientes=r.multas_pendientes,
            multas_saldo=r.multas_saldo, alertas=len(r.alertas),
        ),
        alertas=[AlertaResumenOut(tipo=a.tipo, titulo=a.titulo, detalle=a.detalle, cuando=a.cuando, ruta=a.ruta)
                 for a in r.alertas],
        hoy=[SesionHoyOut(**{**s.__dict__, "sin_marcar": s.sin_marcar}) for s in r.hoy],
        rifas=[RifaAnioOut(**x.__dict__) for x in r.rifas],
        cartera=[CarteraOut(concepto=c, nota=n, monto=m) for c, n, m in r.cartera],
        proximo_torneo=TorneoProximoOut(**r.proximo_torneo) if r.proximo_torneo else None,
    )
