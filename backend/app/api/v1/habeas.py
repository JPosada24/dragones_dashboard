"""Solicitudes de habeas data (Ley 1581). Quien tenga `habeas.gestionar` (SuperAdmin y Admin)."""
import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import ip_cliente, requiere
from app.db.session import get_db
from app.models.acceso import Usuario
from app.schemas.habeas import ProrrogaSolicitudIn, RespuestaIn, SolicitudIn, SolicitudOut
from app.services import habeas as servicio

router = APIRouter(prefix="/habeas", tags=["habeas"])
GESTIONAR = requiere("habeas.gestionar")


@router.get("", response_model=list[SolicitudOut])
def listar(
    estado: str | None = Query(None, pattern="^(en_tramite|respondida)$"),
    _: Usuario = Depends(GESTIONAR),
    db: Session = Depends(get_db),
) -> list[SolicitudOut]:
    return [SolicitudOut(**servicio.a_salida(s)) for s in servicio.listar(db, estado)]


@router.post("", response_model=SolicitudOut, status_code=status.HTTP_201_CREATED)
def registrar(
    datos: SolicitudIn, request: Request, actor: Usuario = Depends(GESTIONAR), db: Session = Depends(get_db),
) -> SolicitudOut:
    s = servicio.registrar(db, datos.model_dump(), actor=actor, ip=ip_cliente(request))
    db.commit()
    return SolicitudOut(**servicio.a_salida(s))


@router.post("/{solicitud_id}/prorrogar", response_model=SolicitudOut)
def prorrogar(
    solicitud_id: uuid.UUID, datos: ProrrogaSolicitudIn, request: Request,
    actor: Usuario = Depends(GESTIONAR), db: Session = Depends(get_db),
) -> SolicitudOut:
    s = servicio.prorrogar(db, servicio.obtener(db, solicitud_id), datos.motivo, actor=actor, ip=ip_cliente(request))
    db.commit()
    return SolicitudOut(**servicio.a_salida(s))


@router.post("/{solicitud_id}/responder", response_model=SolicitudOut)
def responder(
    solicitud_id: uuid.UUID, datos: RespuestaIn, request: Request,
    actor: Usuario = Depends(GESTIONAR), db: Session = Depends(get_db),
) -> SolicitudOut:
    s = servicio.responder(db, servicio.obtener(db, solicitud_id), datos.respuesta, actor=actor, ip=ip_cliente(request))
    db.commit()
    return SolicitudOut(**servicio.a_salida(s))
