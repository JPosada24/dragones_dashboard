import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import ip_cliente, requiere, requiere_alguno
from app.core.fechas import hoy
from app.db.session import get_db
from app.models.acceso import Usuario
from app.models.alumnos import Inscripcion
from app.schemas.comunes import Rama
from app.schemas.inscripciones import (
    AnulacionIn, EstadoIn, EstadoInscripcion, InscripcionCrear, InscripcionOut, PagoIn, PagoOut, ProrrogaIn, ProrrogaOut,
    VencidasOut,
)
from app.services import inscripciones as servicio

router = APIRouter(prefix="/inscripciones", tags=["inscripciones"])

VER = requiere_alguno("alumnos.ver_todos", "alumnos.ver_rama", "alumnos.ver_propios")


def _pagos_out(i: Inscripcion) -> list[PagoOut]:
    anulados = {p.anula_id for p in i.pagos if p.anula_id}
    return [
        PagoOut(
            id=p.id, fecha=p.fecha, monto=p.monto, anula_id=p.anula_id, anulado=p.id in anulados, motivo=p.motivo,
            registrado_por=p.registrado_por, creado_en=p.creado_en,
        )
        for p in i.pagos
    ]


def inscripcion_a_out(i: Inscripcion) -> InscripcionOut:
    return InscripcionOut(
        id=i.id,
        alumno_id=i.alumno_id,
        alumno_nombre=f"{i.alumno.nombres} {i.alumno.apellidos}",
        anio=i.anio,
        rama=i.rama,
        fecha_inscripcion=i.fecha_inscripcion,
        fecha_limite_pago=i.fecha_limite_pago,
        valor=i.valor,
        fecha_pago=i.fecha_pago,
        monto_pagado=i.monto_pagado,
        saldo=i.saldo,
        estado=i.estado,
        causa_rechazo=i.causa_rechazo,
        motivo=i.motivo,
        prorrogas=[ProrrogaOut.model_validate(p) for p in i.prorrogas],
        pagos=_pagos_out(i),
    )


@router.get("", response_model=list[InscripcionOut])
def listar(
    estado: EstadoInscripcion | None = None,
    anio: int | None = Query(None, ge=2000, le=2100),
    rama: Rama | None = None,
    alumno_id: uuid.UUID | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    usuario: Usuario = Depends(VER),
    db: Session = Depends(get_db),
) -> list[InscripcionOut]:
    filas = servicio.listar(
        db, usuario, estado=estado, anio=anio, rama=rama, alumno_id=alumno_id, skip=skip, limit=limit
    )
    return [inscripcion_a_out(i) for i in filas]


@router.post("", response_model=InscripcionOut, status_code=status.HTTP_201_CREATED)
def crear(
    datos: InscripcionCrear,
    request: Request,
    actor: Usuario = Depends(requiere("inscripciones.crear")),
    db: Session = Depends(get_db),
) -> InscripcionOut:
    i = servicio.crear(
        db, alumno_id=datos.alumno_id, fecha_inscripcion=datos.fecha_inscripcion, actor=actor, ip=ip_cliente(request)
    )
    db.commit()
    return inscripcion_a_out(i)


@router.post("/vencer", response_model=VencidasOut)
def vencer(
    request: Request,
    actor: Usuario = Depends(requiere("inscripciones.gestionar")),
    db: Session = Depends(get_db),
) -> VencidasOut:
    """Rechaza las pendientes con plazo vencido. Mientras no exista el worker diario, se puede lanzar a mano."""
    n = servicio.vencer(db, en=hoy(), actor_id=actor.id, ip=ip_cliente(request))
    db.commit()
    return VencidasOut(vencidas=n)


@router.get("/{inscripcion_id}", response_model=InscripcionOut)
def detalle(
    inscripcion_id: uuid.UUID, usuario: Usuario = Depends(VER), db: Session = Depends(get_db)
) -> InscripcionOut:
    return inscripcion_a_out(servicio.obtener_visible(db, usuario, inscripcion_id))


@router.post("/{inscripcion_id}/pagos", response_model=InscripcionOut)
def registrar_pago(
    inscripcion_id: uuid.UUID,
    datos: PagoIn,
    request: Request,
    actor: Usuario = Depends(requiere("inscripciones.abonar")),  # el Entrenador llega filtrado a su rama
    db: Session = Depends(get_db),
) -> InscripcionOut:
    i = servicio.obtener_visible(db, actor, inscripcion_id)
    servicio.registrar_pago(db, i, fecha_pago=datos.fecha_pago, monto=datos.monto, actor=actor, ip=ip_cliente(request))
    db.commit()
    return inscripcion_a_out(i)


@router.post("/{inscripcion_id}/pagos/{pago_id}/anular", response_model=InscripcionOut)
def anular_pago(
    inscripcion_id: uuid.UUID,
    pago_id: uuid.UUID,
    datos: AnulacionIn,
    request: Request,
    actor: Usuario = Depends(requiere("pagos.anular")),
    db: Session = Depends(get_db),
) -> InscripcionOut:
    i = servicio.obtener_visible(db, actor, inscripcion_id)
    servicio.anular_pago(db, i, pago_id=pago_id, motivo=datos.motivo, actor=actor, ip=ip_cliente(request))
    db.commit()
    return inscripcion_a_out(i)


@router.post("/{inscripcion_id}/prorroga", response_model=InscripcionOut)
def conceder_prorroga(
    inscripcion_id: uuid.UUID,
    datos: ProrrogaIn,
    request: Request,
    actor: Usuario = Depends(requiere("prorroga.conceder")),
    db: Session = Depends(get_db),
) -> InscripcionOut:
    i = servicio.obtener_visible(db, actor, inscripcion_id)
    servicio.conceder_prorroga(
        db, i, nuevo_limite=datos.nueva_fecha_limite, motivo=datos.motivo, actor=actor, ip=ip_cliente(request)
    )
    db.commit()
    return inscripcion_a_out(i)


@router.post("/{inscripcion_id}/estado", response_model=InscripcionOut)
def cambiar_estado(
    inscripcion_id: uuid.UUID,
    datos: EstadoIn,
    request: Request,
    actor: Usuario = Depends(requiere("inscripciones.gestionar")),
    db: Session = Depends(get_db),
) -> InscripcionOut:
    i = servicio.obtener_visible(db, actor, inscripcion_id)
    servicio.cambiar_estado(db, i, nuevo=datos.estado, motivo=datos.motivo, actor=actor, ip=ip_cliente(request))
    db.commit()
    return inscripcion_a_out(i)
