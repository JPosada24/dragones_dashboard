import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import ip_cliente, requiere, requiere_alguno
from app.core import fechas
from app.db.session import get_db
from app.models.acceso import Usuario
from app.models.asistencia import Sesion
from app.schemas.asistencia import (
    AlertaOut, CancelarIn, CierreOut, CorreccionIn, FilaPlanillaOut, JustificacionOut, JustificarIn, MarcarGrupoIn,
    MarcarPropiaIn, SesionCrear, SesionOut, SesionProgramar,
)
from app.schemas.comunes import Rama
from app.services import asistencia as servicio

router = APIRouter(prefix="/sesiones", tags=["asistencia"])

VER = requiere_alguno("alumnos.ver_todos", "alumnos.ver_rama", "alumnos.ver_propios")


def sesion_a_out(s: Sesion) -> SesionOut:
    return SesionOut(
        id=s.id, rama=s.rama, fecha=s.fecha, hora_inicio=s.hora_inicio, hora_fin=s.hora_fin, lugar=s.lugar,
        cancelada=s.cancelada, motivo_cancelacion=s.motivo_cancelacion, cerrada=s.cerrada_en is not None,
    )


def justificacion_a_out(j) -> JustificacionOut:
    return JustificacionOut(
        id=j.id, sesion_id=j.sesion_id, fecha_sesion=j.sesion.fecha, rama=j.sesion.rama, alumno_id=j.alumno_id,
        alumno_nombre=f"{j.alumno.nombres} {j.alumno.apellidos}", motivo=j.motivo, estado=j.estado,
        comentario=j.comentario, creado_en=j.creado_en, revisada_en=j.revisada_en,
    )


@router.get("", response_model=list[SesionOut])
def listar(
    desde: date | None = None,
    hasta: date | None = None,
    rama: Rama | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    usuario: Usuario = Depends(VER),
    db: Session = Depends(get_db),
) -> list[SesionOut]:
    filas = servicio.listar(db, usuario, desde=desde, hasta=hasta, rama=rama, skip=skip, limit=limit)
    return [sesion_a_out(s) for s in filas]


@router.post("", response_model=SesionOut, status_code=status.HTTP_201_CREATED)
def crear(
    datos: SesionCrear,
    request: Request,
    actor: Usuario = Depends(requiere("sesiones.gestionar")),
    db: Session = Depends(get_db),
) -> SesionOut:
    [sesion] = servicio.programar(
        db, rama=datos.rama, desde=datos.fecha, hasta=datos.fecha, dias_semana=[datos.fecha.weekday()],
        hora_inicio=datos.hora_inicio, hora_fin=datos.hora_fin, lugar=datos.lugar, actor=actor, ip=ip_cliente(request),
    )
    db.commit()
    return sesion_a_out(sesion)


@router.post("/programar", response_model=list[SesionOut], status_code=status.HTTP_201_CREATED)
def programar(
    datos: SesionProgramar,
    request: Request,
    actor: Usuario = Depends(requiere("sesiones.gestionar")),
    db: Session = Depends(get_db),
) -> list[SesionOut]:
    sesiones = servicio.programar(
        db, rama=datos.rama, desde=datos.desde, hasta=datos.hasta, dias_semana=datos.dias_semana,
        hora_inicio=datos.hora_inicio, hora_fin=datos.hora_fin, lugar=datos.lugar, actor=actor, ip=ip_cliente(request),
    )
    db.commit()
    return [sesion_a_out(s) for s in sesiones]


@router.post("/cerrar", response_model=CierreOut)
def cerrar(
    request: Request,
    actor: Usuario = Depends(requiere("asistencia.corregir")),
    db: Session = Depends(get_db),
) -> CierreOut:
    """Cierra las sesiones cuya hora de cierre ya pasó. Mientras no exista el worker nocturno, se lanza a mano."""
    r = servicio.cerrar(db, ahora=fechas.ahora(), actor_id=actor.id, ip=ip_cliente(request))
    db.commit()
    return CierreOut(sesiones=r.sesiones, ausencias=r.ausencias, multas=r.multas)


@router.get("/alertas", response_model=list[AlertaOut])
def alertas(
    usuario: Usuario = Depends(requiere_alguno("alumnos.ver_todos", "asistencia.marcar_grupo")),
    db: Session = Depends(get_db),
) -> list[AlertaOut]:
    return [
        AlertaOut(
            alumno_id=a.alumno.id, alumno_nombre=f"{a.alumno.nombres} {a.alumno.apellidos}", rama=a.alumno.rama,
            inasistencias_seguidas=a.inasistencias_seguidas,
        )
        for a in servicio.alertas(db, usuario)
    ]


@router.get("/{sesion_id}", response_model=SesionOut)
def detalle(sesion_id: uuid.UUID, usuario: Usuario = Depends(VER), db: Session = Depends(get_db)) -> SesionOut:
    return sesion_a_out(servicio.obtener_visible(db, usuario, sesion_id))


@router.post("/{sesion_id}/cancelar", response_model=SesionOut)
def cancelar(
    sesion_id: uuid.UUID,
    datos: CancelarIn,
    request: Request,
    actor: Usuario = Depends(requiere("sesiones.gestionar")),
    db: Session = Depends(get_db),
) -> SesionOut:
    sesion = servicio.obtener_visible(db, actor, sesion_id)
    servicio.cancelar(db, sesion, motivo=datos.motivo, actor=actor, ip=ip_cliente(request))
    db.commit()
    return sesion_a_out(sesion)


@router.get("/{sesion_id}/asistencia", response_model=list[FilaPlanillaOut])
def planilla(
    sesion_id: uuid.UUID, usuario: Usuario = Depends(VER), db: Session = Depends(get_db)
) -> list[FilaPlanillaOut]:
    sesion = servicio.obtener_visible(db, usuario, sesion_id)
    return [
        FilaPlanillaOut(
            alumno_id=f.alumno.id, alumno_nombre=f"{f.alumno.nombres} {f.alumno.apellidos}",
            asistencia=f.asistencia, justificacion=f.justificacion, multa=f.multa,
        )
        for f in servicio.planilla(db, usuario, sesion)
    ]


@router.post("/{sesion_id}/asistencia", response_model=list[FilaPlanillaOut])
def marcar_grupo(
    sesion_id: uuid.UUID,
    datos: MarcarGrupoIn,
    request: Request,
    actor: Usuario = Depends(requiere("asistencia.marcar_grupo")),
    db: Session = Depends(get_db),
) -> list[FilaPlanillaOut]:
    sesion = servicio.obtener_visible(db, actor, sesion_id)
    servicio.marcar_grupo(
        db, sesion, marcas=[(m.alumno_id, m.estado) for m in datos.marcas], actor=actor, ip=ip_cliente(request)
    )
    db.commit()
    return planilla(sesion_id, actor, db)


@router.post("/{sesion_id}/asistencia/propia", status_code=status.HTTP_204_NO_CONTENT)
def marcar_propia(
    sesion_id: uuid.UUID,
    datos: MarcarPropiaIn,
    request: Request,
    actor: Usuario = Depends(requiere("asistencia.marcar_propia")),
    db: Session = Depends(get_db),
) -> None:
    sesion = servicio.obtener_visible(db, actor, sesion_id)
    servicio.marcar_propia(db, sesion, alumno_id=datos.alumno_id, actor=actor, ip=ip_cliente(request))
    db.commit()


@router.patch("/{sesion_id}/asistencia/{alumno_id}", response_model=list[FilaPlanillaOut])
def corregir(
    sesion_id: uuid.UUID,
    alumno_id: uuid.UUID,
    datos: CorreccionIn,
    request: Request,
    actor: Usuario = Depends(requiere("asistencia.corregir")),
    db: Session = Depends(get_db),
) -> list[FilaPlanillaOut]:
    sesion = servicio.obtener_visible(db, actor, sesion_id)
    servicio.corregir(
        db, sesion, alumno_id=alumno_id, estado=datos.estado, motivo=datos.motivo, actor=actor, ip=ip_cliente(request)
    )
    db.commit()
    return planilla(sesion_id, actor, db)


@router.post("/{sesion_id}/justificaciones", response_model=JustificacionOut, status_code=status.HTTP_201_CREATED)
def justificar(
    sesion_id: uuid.UUID,
    datos: JustificarIn,
    request: Request,
    actor: Usuario = Depends(requiere_alguno("asistencia.marcar_propia", "asistencia.marcar_grupo")),
    db: Session = Depends(get_db),
) -> JustificacionOut:
    sesion = servicio.obtener_visible(db, actor, sesion_id)
    j = servicio.justificar(db, sesion, alumno_id=datos.alumno_id, motivo=datos.motivo, actor=actor, ip=ip_cliente(request))
    db.commit()
    return justificacion_a_out(j)
