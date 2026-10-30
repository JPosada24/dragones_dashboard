import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import ip_cliente, requiere, requiere_alguno
from app.db.session import get_db
from app.models.acceso import Usuario
from app.models.asistencia import Multa
from app.schemas.asistencia import MultaAnularIn, MultaOut, MultaPagoIn, MultasPagoIn
from app.schemas.comunes import Rama
from app.services import multas as servicio

router = APIRouter(prefix="/multas", tags=["multas"])


def multa_a_out(m: Multa) -> MultaOut:
    return MultaOut(
        id=m.id, alumno_id=m.alumno_id, alumno_nombre=f"{m.alumno.nombres} {m.alumno.apellidos}",
        rama=m.alumno.rama, sesion_id=m.sesion_id, fecha_sesion=m.sesion.fecha, valor=m.valor, estado=m.estado,
        fecha_pago=m.fecha_pago, motivo_anulacion=m.motivo_anulacion,
    )


@router.get("", response_model=list[MultaOut])
def listar(
    estado: str | None = Query(None, pattern="^(pendiente|pagada|anulada)$"),
    alumno_id: uuid.UUID | None = None,
    rama: Rama | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    usuario: Usuario = Depends(requiere_alguno("alumnos.ver_todos", "alumnos.ver_propios")),
    db: Session = Depends(get_db),
) -> list[MultaOut]:
    filas = servicio.listar(db, usuario, estado=estado, alumno_id=alumno_id, rama=rama, skip=skip, limit=limit)
    return [multa_a_out(m) for m in filas]


@router.post("/pagos", response_model=list[MultaOut])
def pagar_varias(
    datos: MultasPagoIn,
    request: Request,
    actor: Usuario = Depends(requiere("pagos.registrar")),
    db: Session = Depends(get_db),
) -> list[MultaOut]:
    """Cobra varias multas a la vez (todas o ninguna)."""
    filas = servicio.pagar_varias(
        db, actor, multa_ids=datos.multa_ids, fecha_pago=datos.fecha_pago, actor=actor, ip=ip_cliente(request)
    )
    db.commit()
    return [multa_a_out(m) for m in filas]


@router.post("/{multa_id}/pago", response_model=MultaOut)
def pagar(
    multa_id: uuid.UUID,
    datos: MultaPagoIn,
    request: Request,
    actor: Usuario = Depends(requiere("pagos.registrar")),  # Admin/SuperAdmin: el Entrenador no cobra multas
    db: Session = Depends(get_db),
) -> MultaOut:
    m = servicio.obtener_visible(db, actor, multa_id)
    servicio.pagar(db, m, fecha_pago=datos.fecha_pago, actor=actor, ip=ip_cliente(request))
    db.commit()
    return multa_a_out(m)


@router.post("/{multa_id}/anular", response_model=MultaOut)
def anular(
    multa_id: uuid.UUID,
    datos: MultaAnularIn,
    request: Request,
    actor: Usuario = Depends(requiere("multas.anular")),
    db: Session = Depends(get_db),
) -> MultaOut:
    m = servicio.obtener_visible(db, actor, multa_id)
    servicio.anular(db, m, motivo=datos.motivo, actor=actor, ip=ip_cliente(request))
    db.commit()
    return multa_a_out(m)
