import uuid

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import ip_cliente, requiere, usuario_a_out
from app.core.permissions import PERSONALIZABLES
from app.db.session import get_db
from app.models.acceso import Usuario
from app.schemas.auth import (
    PermisoOut,
    PermisosIn,
    PermisosUsuarioOut,
    RolesOut,
    RolOut,
    UsuarioActualizar,
    UsuarioCrear,
    UsuarioListaOut,
    UsuarioOut,
)
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
    return [
        UsuarioListaOut(
            **usuario_a_out(u).model_dump(), vinculado_a=vinculos.get(u.id),
            permisos_personalizados=servicio.permisos_de(u)["personalizable"] and bool(u.ajustes),
        )
        for u in filas
    ]


@router.get("/roles", response_model=RolesOut)
def roles(_: Usuario = Depends(requiere("usuarios.gestionar")), db: Session = Depends(get_db)) -> RolesOut:
    """Quién puede hacer qué según su rol, y qué permisos se pueden ajustar por persona."""
    permisos, filas = servicio.roles_y_permisos(db)
    return RolesOut(
        permisos=[PermisoOut(codigo=p.codigo, descripcion=p.descripcion) for p in permisos],
        roles=[
            RolOut(codigo=r.codigo, nombre=r.nombre, descripcion=r.descripcion,
                   permisos=sorted(p.codigo for p in r.permisos))
            for r in filas
        ],
        personalizables=sorted(PERSONALIZABLES),
    )


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


@router.get("/{usuario_id}/permisos", response_model=PermisosUsuarioOut)
def permisos(
    usuario_id: uuid.UUID, _: Usuario = Depends(requiere("usuarios.gestionar")), db: Session = Depends(get_db),
) -> PermisosUsuarioOut:
    return PermisosUsuarioOut(**servicio.permisos_de(servicio.obtener(db, usuario_id)))


@router.put("/{usuario_id}/permisos", response_model=PermisosUsuarioOut)
def ajustar_permisos(
    usuario_id: uuid.UUID,
    datos: PermisosIn,
    request: Request,
    actor: Usuario = Depends(requiere("usuarios.gestionar")),
    db: Session = Depends(get_db),
) -> PermisosUsuarioOut:
    """Deja a la persona con esos permisos: lo que su rol no trae se le da y lo que trae y no está se le quita."""
    usuario = servicio.ajustar_permisos(
        db, servicio.obtener(db, usuario_id), set(datos.permisos), actor=actor, ip=ip_cliente(request),
    )
    db.commit()
    return PermisosUsuarioOut(**servicio.permisos_de(usuario))


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
