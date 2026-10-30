import uuid

from fastapi import APIRouter, Depends, Query, Request, status
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
    CompradorIn,
    PagoPuestoOut,
    PagoRifaIn,
    PuestoOut,
    RifaCrear,
    RifaOut,
    TalonarioOut,
)
from app.services import rifas as servicio

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
    precio = t.rifa.precio_puesto
    return TalonarioOut(
        id=t.id, alumno_id=t.alumno_id, alumno_nombre=f"{t.alumno.nombres} {t.alumno.apellidos}", rama=t.alumno.rama,
        codigo=t.codigo, desde=t.puestos[0].numero, hasta=t.puestos[-1].numero, recaudado=t.recaudado, saldo=t.saldo,
        pagado=t.pagado,
        puestos=[
            PuestoOut(
                numero=p.numero, boleta=p.numero - t.puestos[0].numero + 1, comprador_nombre=p.comprador_nombre,
                comprador_telefono=p.comprador_telefono,
                monto_pagado=p.monto_pagado, saldo=precio - p.monto_pagado,
                pagos=[PagoPuestoOut.model_validate(x) for x in p.pagos],
            )
            for p in t.puestos
        ],
    )


def acta_a_out(db: Session, a: ActaSorteo) -> ActaOut:
    """El ganador se muestra como código del talonario + boleta (F012-07), con el código que tenía al venderse."""
    t = servicio.talonario_de(db, a.rifa_id, a.alumno_id)
    return ActaOut(
        rifa_id=a.rifa_id, numero_ganador=a.numero_ganador, codigo=t.codigo,
        boleta=a.numero_ganador - t.puestos[0].numero + 1, alumno_id=a.alumno_id,
        alumno_nombre=f"{t.alumno.nombres} {t.alumno.apellidos}", rama=t.alumno.rama,
        comprador_nombre=a.comprador_nombre, total_participantes=a.total_participantes,
        participantes=a.participantes, huella=a.huella, jugado_en=a.jugado_en,
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


@router.patch("/{rifa_id}/puestos/{numero}", response_model=TalonarioOut)
def actualizar_comprador(
    rifa_id: uuid.UUID,
    numero: int,
    datos: CompradorIn,
    request: Request,
    actor: Usuario = Depends(requiere("rifas.gestionar")),
    db: Session = Depends(get_db),
) -> TalonarioOut:
    rifa = servicio.obtener(db, rifa_id)
    puesto = servicio.actualizar_comprador(
        db, rifa, numero, nombre=datos.nombre, telefono=datos.telefono, actor=actor, ip=ip_cliente(request)
    )
    db.commit()
    return talonario_a_out(db.get(Talonario, puesto.talonario_id))


@router.post("/{rifa_id}/puestos/{numero}/pagos", response_model=TalonarioOut)
def pagar_puesto(
    rifa_id: uuid.UUID,
    numero: int,
    datos: PagoRifaIn,
    request: Request,
    actor: Usuario = Depends(requiere("pagos.registrar")),
    db: Session = Depends(get_db),
) -> TalonarioOut:
    rifa = servicio.obtener(db, rifa_id)
    puesto = servicio.pagar_puesto(
        db, rifa, numero, monto=datos.monto, fecha=datos.fecha, actor=actor, ip=ip_cliente(request)
    )
    db.commit()
    return talonario_a_out(db.get(Talonario, puesto.talonario_id))


@router.post("/{rifa_id}/puestos/{numero}/pagos/{pago_id}/anular", response_model=TalonarioOut)
def anular_pago(
    rifa_id: uuid.UUID,
    numero: int,
    pago_id: uuid.UUID,
    datos: AnularPagoRifaIn,
    request: Request,
    actor: Usuario = Depends(requiere("pagos.anular")),
    db: Session = Depends(get_db),
) -> TalonarioOut:
    rifa = servicio.obtener(db, rifa_id)
    puesto = servicio.anular_pago(db, rifa, numero, pago_id, motivo=datos.motivo, actor=actor, ip=ip_cliente(request))
    db.commit()
    return talonario_a_out(db.get(Talonario, puesto.talonario_id))


@router.post("/{rifa_id}/sorteo", response_model=ActaOut, status_code=status.HTTP_201_CREATED)
def sortear(
    rifa_id: uuid.UUID,
    request: Request,
    actor: Usuario = Depends(requiere("sorteo.jugar")),
    db: Session = Depends(get_db),
) -> ActaOut:
    a = servicio.sortear(db, servicio.obtener(db, rifa_id), actor=actor, ip=ip_cliente(request))
    db.commit()
    return acta_a_out(db, a)


@router.get("/{rifa_id}/acta", response_model=ActaOut)
def ver_acta(rifa_id: uuid.UUID, _: Usuario = Depends(VER), db: Session = Depends(get_db)) -> ActaOut:
    a = servicio.acta(db, servicio.obtener(db, rifa_id))
    return acta_a_out(db, a)
