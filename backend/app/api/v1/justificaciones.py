import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import ip_cliente, requiere, requiere_alguno
from app.api.v1.sesiones import justificacion_a_out
from app.db.session import get_db
from app.models.acceso import Usuario
from app.schemas.asistencia import JustificacionOut, RevisarIn
from app.services import asistencia as servicio

router = APIRouter(prefix="/justificaciones", tags=["asistencia"])


@router.get("", response_model=list[JustificacionOut])
def listar(
    estado: str | None = Query(None, pattern="^(pendiente|aprobada|rechazada)$"),
    alumno_id: uuid.UUID | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    usuario: Usuario = Depends(requiere_alguno("alumnos.ver_todos", "alumnos.ver_propios")),
    db: Session = Depends(get_db),
) -> list[JustificacionOut]:
    filas = servicio.listar_justificaciones(db, usuario, estado=estado, alumno_id=alumno_id, skip=skip, limit=limit)
    return [justificacion_a_out(j) for j in filas]


@router.post("/{justificacion_id}/revisar", response_model=JustificacionOut)
def revisar(
    justificacion_id: uuid.UUID,
    datos: RevisarIn,
    request: Request,
    actor: Usuario = Depends(requiere("justificaciones.revisar")),
    db: Session = Depends(get_db),
) -> JustificacionOut:
    j = servicio.obtener_justificacion(db, actor, justificacion_id)
    servicio.revisar(db, j, aprobar=datos.aprobar, comentario=datos.comentario, actor=actor, ip=ip_cliente(request))
    db.commit()
    return justificacion_a_out(j)
