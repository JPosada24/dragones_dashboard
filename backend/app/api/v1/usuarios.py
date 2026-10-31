import uuid

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import ip_cliente, requiere, usuario_a_out
from app.db.session import get_db
from app.models.acceso import Usuario
from app.schemas.auth import UsuarioActualizar, UsuarioCrear, UsuarioListaOut, UsuarioOut
from app.services import usuarios as servicio

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


@router.get("", response_model=list[UsuarioListaOut])
def listar(
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
    _: Usuario = Depends(requiere("usuarios.gestionar")),
    db: Session = Depends(get_db),
) -> list[UsuarioListaOut]:
    filas = servicio.listar(db, skip=skip, limit=limit)
    vinculos = servicio.vinculos(db, [u.id for u in filas])
    return [UsuarioListaOut(**usuario_a_out(u).model_dump(), vinculado_a=vinculos.get(u.id)) for u in filas]


@router.post("", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def crear(
    datos: UsuarioCrear,
    request: Request,
    actor: Usuario = Depends(requiere("usuarios.gestionar")),
    db: Session = Depends(get_db),
) -> UsuarioOut:
    usuario = servicio.crear_cuenta(db, datos.model_dump(), actor=actor, ip=ip_cliente(request))
    db.commit()
    return usuario_a_out(usuario)


@router.patch("/{usuario_id}", response_model=UsuarioOut)
def actualizar(
    usuario_id: uuid.UUID,
    datos: UsuarioActualizar,
    request: Request,
    actor: Usuario = Depends(requiere("usuarios.gestionar")),
    db: Session = Depends(get_db),
) -> UsuarioOut:
    usuario = servicio.actualizar_usuario(
        db, servicio.obtener(db, usuario_id), datos.model_dump(exclude_unset=True), actor=actor, ip=ip_cliente(request),
    )
    db.commit()
    return usuario_a_out(usuario)


@router.delete("/{usuario_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar(
    usuario_id: uuid.UUID,
    request: Request,
    actor: Usuario = Depends(requiere("usuarios.eliminar")),  # solo el SuperAdmin
    db: Session = Depends(get_db),
) -> Response:
    servicio.eliminar_usuario(db, servicio.obtener(db, usuario_id), actor=actor, ip=ip_cliente(request))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
