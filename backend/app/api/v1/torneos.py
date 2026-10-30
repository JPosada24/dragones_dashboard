import uuid
from datetime import date

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import ip_cliente, requiere
from app.db.session import get_db
from app.models.acceso import Usuario
from app.models.torneos import Torneo
from app.schemas.torneos import (
    AnularPagoEquipoIn,
    EquipoCrear,
    EquipoOut,
    MotivoIn,
    PagoEquipoIn,
    RetiroOut,
    TorneoActualizar,
    TorneoCrear,
    TorneoOut,
)
from app.services import torneos as servicio
from app.services.errores import Prohibido

# Los torneos guardan datos de contacto de delegados externos: solo los ve quien los gestiona.
router = APIRouter(prefix="/torneos", tags=["torneos"])
GESTIONAR = requiere("eventos.gestionar")


def torneo_a_out(db: Session, t: Torneo) -> TorneoOut:
    return TorneoOut(
        id=t.id, nombre=t.nombre, rama=t.rama, fecha_inicio=t.fecha_inicio, fecha_fin=t.fecha_fin,
        fecha_limite_inscripcion=t.fecha_limite_inscripcion, lugar=t.lugar, cupo_equipos=t.cupo_equipos,
        valor_inscripcion=t.valor_inscripcion, estado=t.estado, motivo_cancelacion=t.motivo_cancelacion,
        **servicio.resumen(db, t),
    )


@router.get("", response_model=list[TorneoOut])
def listar(
    desde: date | None = None, _: Usuario = Depends(GESTIONAR), db: Session = Depends(get_db)
) -> list[TorneoOut]:
    return [torneo_a_out(db, t) for t in servicio.listar(db, desde=desde)]


@router.post("", response_model=TorneoOut, status_code=status.HTTP_201_CREATED)
def crear(
    datos: TorneoCrear, request: Request, actor: Usuario = Depends(GESTIONAR), db: Session = Depends(get_db)
) -> TorneoOut:
    t = servicio.crear(db, datos=datos.model_dump(), actor=actor, ip=ip_cliente(request))
    db.commit()
    return torneo_a_out(db, t)


@router.get("/{torneo_id}", response_model=TorneoOut)
def detalle(torneo_id: uuid.UUID, _: Usuario = Depends(GESTIONAR), db: Session = Depends(get_db)) -> TorneoOut:
    return torneo_a_out(db, servicio.obtener(db, torneo_id))


@router.patch("/{torneo_id}", response_model=TorneoOut)
def actualizar(
    torneo_id: uuid.UUID, datos: TorneoActualizar, request: Request,
    actor: Usuario = Depends(GESTIONAR), db: Session = Depends(get_db),
) -> TorneoOut:
    t = servicio.actualizar(
        db, servicio.obtener(db, torneo_id), cambios=datos.model_dump(exclude_unset=True), actor=actor,
        ip=ip_cliente(request),
    )
    db.commit()
    return torneo_a_out(db, t)


@router.delete("/{torneo_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(
    torneo_id: uuid.UUID, request: Request, actor: Usuario = Depends(GESTIONAR), db: Session = Depends(get_db),
) -> Response:
    """Quita el torneo de todas las vistas. Si ya recibió pagos, solo el SuperAdmin puede."""
    t = servicio.obtener(db, torneo_id)
    if servicio.resumen(db, t)["recaudado"] and "pagos.anular" not in actor.permisos_codigos:
        raise Prohibido("Este torneo ya tiene pagos: solo el SuperAdmin puede eliminarlo.")
    servicio.eliminar(db, t, actor=actor, ip=ip_cliente(request))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{torneo_id}/cancelar", response_model=TorneoOut)
def cancelar(
    torneo_id: uuid.UUID, datos: MotivoIn, request: Request,
    actor: Usuario = Depends(GESTIONAR), db: Session = Depends(get_db),
) -> TorneoOut:
    t = servicio.cancelar(db, servicio.obtener(db, torneo_id), motivo=datos.motivo, actor=actor, ip=ip_cliente(request))
    db.commit()
    return torneo_a_out(db, t)


@router.get("/{torneo_id}/equipos", response_model=list[EquipoOut])
def equipos(torneo_id: uuid.UUID, _: Usuario = Depends(GESTIONAR), db: Session = Depends(get_db)) -> list[EquipoOut]:
    return [EquipoOut.model_validate(e) for e in servicio.listar_equipos(db, servicio.obtener(db, torneo_id))]


@router.post("/{torneo_id}/equipos", response_model=EquipoOut, status_code=status.HTTP_201_CREATED)
def inscribir(
    torneo_id: uuid.UUID, datos: EquipoCrear, request: Request,
    actor: Usuario = Depends(GESTIONAR), db: Session = Depends(get_db),
) -> EquipoOut:
    e = servicio.inscribir(db, servicio.obtener(db, torneo_id), datos=datos.model_dump(), actor=actor,
                           ip=ip_cliente(request))
    db.commit()
    return EquipoOut.model_validate(e)


@router.post("/{torneo_id}/equipos/{equipo_id}/retirar", response_model=RetiroOut)
def retirar(
    torneo_id: uuid.UUID, equipo_id: uuid.UUID, datos: MotivoIn, request: Request,
    actor: Usuario = Depends(GESTIONAR), db: Session = Depends(get_db),
) -> RetiroOut:
    torneo = servicio.obtener(db, torneo_id)
    equipo = servicio.obtener_equipo(db, torneo, equipo_id)
    promovido = servicio.retirar(db, torneo, equipo, motivo=datos.motivo, actor=actor, ip=ip_cliente(request))
    db.commit()
    return RetiroOut(
        retirado=EquipoOut.model_validate(equipo),
        promovido=EquipoOut.model_validate(promovido) if promovido else None,
    )


@router.post("/{torneo_id}/equipos/{equipo_id}/pagos", response_model=EquipoOut)
def pagar(
    torneo_id: uuid.UUID, equipo_id: uuid.UUID, datos: PagoEquipoIn, request: Request,
    actor: Usuario = Depends(requiere("pagos.registrar")), db: Session = Depends(get_db),
) -> EquipoOut:
    equipo = servicio.obtener_equipo(db, servicio.obtener(db, torneo_id), equipo_id)
    servicio.pagar(db, equipo, monto=datos.monto, fecha=datos.fecha, actor=actor, ip=ip_cliente(request))
    db.commit()
    return EquipoOut.model_validate(equipo)


@router.post("/{torneo_id}/equipos/{equipo_id}/pagos/{pago_id}/anular", response_model=EquipoOut)
def anular_pago(
    torneo_id: uuid.UUID, equipo_id: uuid.UUID, pago_id: uuid.UUID, datos: AnularPagoEquipoIn, request: Request,
    actor: Usuario = Depends(requiere("pagos.anular")), db: Session = Depends(get_db),
) -> EquipoOut:
    equipo = servicio.obtener_equipo(db, servicio.obtener(db, torneo_id), equipo_id)
    servicio.anular_pago(db, equipo, pago_id, motivo=datos.motivo, actor=actor, ip=ip_cliente(request))
    db.commit()
    return EquipoOut.model_validate(equipo)
