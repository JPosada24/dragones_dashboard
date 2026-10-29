import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import ip_cliente, requiere
from app.db.session import get_db
from app.models.acceso import Usuario
from app.models.alumnos import Acudiente
from app.schemas.alumnos import AcudienteActualizar, AcudienteCrear, AcudienteOut
from app.schemas.comunes import TipoDocumento, normalizar_documento
from app.services import alumnos as servicio
from app.services.errores import ErrorNegocio

router = APIRouter(prefix="/acudientes", tags=["acudientes"])


def acudiente_a_out(a: Acudiente) -> AcudienteOut:
    return AcudienteOut(
        id=a.id, nombres=a.nombres, apellidos=a.apellidos, tipo_documento=a.tipo_documento,
        documento=servicio.enmascarar(a.documento_ultimos), telefono=a.telefono, email=a.email,
        usuario_id=a.usuario_id,
    )


@router.get("", response_model=list[AcudienteOut])
def listar(
    tipo_documento: TipoDocumento | None = None,
    documento: str | None = Query(None, max_length=30),
    buscar: str | None = Query(None, min_length=2, max_length=80),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    usuario: Usuario = Depends(requiere("alumnos.editar")),
    db: Session = Depends(get_db),
) -> list[AcudienteOut]:
    if documento:
        try:
            documento = normalizar_documento(documento)
        except ValueError as e:
            raise ErrorNegocio(str(e))
    filas = servicio.listar_acudientes(
        db, usuario, tipo_documento=tipo_documento, documento=documento, buscar=buscar, skip=skip, limit=limit
    )
    return [acudiente_a_out(a) for a in filas]


@router.post("", response_model=AcudienteOut, status_code=status.HTTP_201_CREATED)
def crear(
    datos: AcudienteCrear,
    request: Request,
    actor: Usuario = Depends(requiere("alumnos.editar")),
    db: Session = Depends(get_db),
) -> AcudienteOut:
    acudiente = servicio.crear_acudiente(db, datos=datos.model_dump(), actor=actor, ip=ip_cliente(request))
    db.commit()
    return acudiente_a_out(acudiente)


@router.get("/{acudiente_id}", response_model=AcudienteOut)
def detalle(
    acudiente_id: uuid.UUID, usuario: Usuario = Depends(requiere("alumnos.editar")), db: Session = Depends(get_db)
) -> AcudienteOut:
    return acudiente_a_out(servicio.obtener_acudiente(db, usuario, acudiente_id))


@router.patch("/{acudiente_id}", response_model=AcudienteOut)
def actualizar(
    acudiente_id: uuid.UUID,
    datos: AcudienteActualizar,
    request: Request,
    actor: Usuario = Depends(requiere("alumnos.editar")),
    db: Session = Depends(get_db),
) -> AcudienteOut:
    acudiente = servicio.obtener_acudiente(db, actor, acudiente_id)
    servicio.actualizar_acudiente(
        db, acudiente, cambios=datos.model_dump(exclude_unset=True), actor=actor, ip=ip_cliente(request)
    )
    db.commit()
    return acudiente_a_out(acudiente)
