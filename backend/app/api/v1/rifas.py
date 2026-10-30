import uuid

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import ip_cliente, requiere, requiere_alguno
from app.db.session import get_db
from app.models.acceso import Usuario
from app.models.rifas import ActaSorteo, Rifa, Talonario
from app.schemas.rifas import (
    ActaOut,
    AnularPagoRifaIn,
    AsignadosOut,
    CancelarRifaIn,
    PagoRifaIn,
    PagoTalonarioOut,
    RifaCrear,
    RifaOut,
    TalonarioOut,
)
from app.services import rifas as servicio
from app.services.errores import Prohibido

router = APIRouter(prefix="/rifas", tags=["rifas"])

VER = requiere_alguno("alumnos.ver_todos", "alumnos.ver_rama", "alumnos.ver_propios")


def rifa_a_out(db: Session, r: Rifa) -> RifaOut:
    return RifaOut(
        id=r.id, nombre=r.nombre, anio=r.anio, numero=r.numero, premio=r.premio, fecha_sorteo=r.fecha_sorteo,
        puestos_por_talonario=r.puestos_por_talonario, precio_puesto=r.precio_puesto,
        valor_talonario=r.valor_talonario, estado=r.estado, motivo_cancelacion=r.motivo_cancelacion,
        **servicio.resumen(db, r),
    )


def talonario_a_out(t: Talonario) -> TalonarioOut:
    return TalonarioOut(
        id=t.id, alumno_id=t.alumno_id, alumno_nombre=f"{t.alumno.nombres} {t.alumno.apellidos}", rama=t.alumno.rama,
        codigo=t.codigo, boletas=t.rifa.puestos_por_talonario, recaudado=t.recaudado, saldo=t.saldo, pagado=t.pagado,
        pagos=[PagoTalonarioOut.model_validate(p) for p in t.pagos],
    )


def acta_a_out(db: Session, a: ActaSorteo) -> ActaOut:
    """El ganador es el dueño del talonario; la boleta se lee código-número (F012-07)."""
    t = db.get(Talonario, a.talonario_id)
    return ActaOut(
        id=a.id, rifa_id=a.rifa_id, orden=a.orden, codigo=a.codigo, boleta=a.boleta, alumno_id=a.alumno_id,
        alumno_nombre=f"{t.alumno.nombres} {t.alumno.apellidos}", rama=t.alumno.rama,
        total_participantes=a.total_participantes, participantes=a.participantes, huella=a.huella,
        jugado_en=a.jugado_en,
    )


@router.get("", response_model=list[RifaOut])
def listar(
    anio: int | None = Query(None, ge=2000, le=2100), _: Usuario = Depends(VER), db: Session = Depends(get_db)
) -> list[RifaOut]:
    return [rifa_a_out(db, r) for r in servicio.listar(db, anio=anio)]


@router.post("", response_model=RifaOut, status_code=status.HTTP_201_CREATED)
def crear(
    datos: RifaCrear,
    request: Request,
    actor: Usuario = Depends(requiere("rifas.gestionar")),
    db: Session = Depends(get_db),
) -> RifaOut:
    rifa = servicio.crear(db, **datos.model_dump(), actor=actor, ip=ip_cliente(request))
    db.commit()
    return rifa_a_out(db, rifa)


@router.get("/{rifa_id}", response_model=RifaOut)
def detalle(rifa_id: uuid.UUID, _: Usuario = Depends(VER), db: Session = Depends(get_db)) -> RifaOut:
    return rifa_a_out(db, servicio.obtener(db, rifa_id))


@router.post("/{rifa_id}/cancelar", response_model=RifaOut)
def cancelar(
    rifa_id: uuid.UUID,
    datos: CancelarRifaIn,
    request: Request,
    actor: Usuario = Depends(requiere("rifas.gestionar")),
    db: Session = Depends(get_db),
) -> RifaOut:
    rifa = servicio.cancelar(
        db, servicio.obtener(db, rifa_id), motivo=datos.motivo, actor=actor, ip=ip_cliente(request)
    )
    db.commit()
    return rifa_a_out(db, rifa)


@router.delete("/{rifa_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(
    rifa_id: uuid.UUID,
    request: Request,
    actor: Usuario = Depends(requiere("rifas.gestionar")),
    db: Session = Depends(get_db),
) -> Response:
    """Quita la rifa de todas las vistas y cuentas. Si ya tiene dinero o sorteos, solo el SuperAdmin puede."""
    rifa = servicio.obtener(db, rifa_id)
    r = servicio.resumen(db, rifa)
    if (r["recaudado"] or servicio.actas(db, rifa)) and "pagos.anular" not in actor.permisos_codigos:
        raise Prohibido("Esta rifa ya tiene pagos o sorteos: solo el SuperAdmin puede eliminarla.")
    servicio.eliminar(db, rifa, actor=actor, ip=ip_cliente(request))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{rifa_id}/talonarios", response_model=AsignadosOut)
def asignar_talonarios(
    rifa_id: uuid.UUID,
    request: Request,
    actor: Usuario = Depends(requiere("rifas.gestionar")),
    db: Session = Depends(get_db),
) -> AsignadosOut:
    """Da talonario a los alumnos inscritos después de crear la rifa."""
    n = servicio.asignar_pendientes(db, servicio.obtener(db, rifa_id), actor=actor, ip=ip_cliente(request))
    db.commit()
    return AsignadosOut(asignados=n)


@router.get("/{rifa_id}/talonarios", response_model=list[TalonarioOut])
def talonarios(
    rifa_id: uuid.UUID, usuario: Usuario = Depends(VER), db: Session = Depends(get_db)
) -> list[TalonarioOut]:
    rifa = servicio.obtener(db, rifa_id)
    return [talonario_a_out(t) for t in servicio.talonarios_visibles(db, usuario, rifa)]


@router.post("/{rifa_id}/talonarios/{talonario_id}/pagos", response_model=TalonarioOut)
def pagar_talonario(
    rifa_id: uuid.UUID,
    talonario_id: uuid.UUID,
    datos: PagoRifaIn,
    request: Request,
    actor: Usuario = Depends(requiere("pagos.registrar")),
    db: Session = Depends(get_db),
) -> TalonarioOut:
    t = servicio.pagar_talonario(
        db, servicio.obtener(db, rifa_id), talonario_id, monto=datos.monto, fecha=datos.fecha, actor=actor,
        ip=ip_cliente(request),
    )
    db.commit()
    return talonario_a_out(t)


@router.post("/{rifa_id}/talonarios/{talonario_id}/pagos/{pago_id}/anular", response_model=TalonarioOut)
def anular_pago(
    rifa_id: uuid.UUID,
    talonario_id: uuid.UUID,
    pago_id: uuid.UUID,
    datos: AnularPagoRifaIn,
    request: Request,
    actor: Usuario = Depends(requiere("pagos.anular")),
    db: Session = Depends(get_db),
) -> TalonarioOut:
    t = servicio.anular_pago(
        db, servicio.obtener(db, rifa_id), talonario_id, pago_id, motivo=datos.motivo, actor=actor,
        ip=ip_cliente(request),
    )
    db.commit()
    return talonario_a_out(t)


@router.post("/{rifa_id}/sorteo", response_model=ActaOut, status_code=status.HTTP_201_CREATED)
def sortear(
    rifa_id: uuid.UUID,
    request: Request,
    actor: Usuario = Depends(requiere("sorteo.jugar")),
    db: Session = Depends(get_db),
) -> ActaOut:
    """Una jugada del sorteo. Se puede repetir: cada jugada deja su acta y una boleta no gana dos veces."""
    a = servicio.sortear(db, servicio.obtener(db, rifa_id), actor=actor, ip=ip_cliente(request))
    db.commit()
    return acta_a_out(db, a)


@router.get("/{rifa_id}/actas", response_model=list[ActaOut])
def ver_actas(rifa_id: uuid.UUID, _: Usuario = Depends(VER), db: Session = Depends(get_db)) -> list[ActaOut]:
    """Las jugadas del sorteo de esta rifa, en orden."""
    return [acta_a_out(db, a) for a in servicio.actas(db, servicio.obtener(db, rifa_id))]
