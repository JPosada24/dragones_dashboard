import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import ip_cliente, requiere, usuario_a_out
from app.db.session import get_db
from app.models.acceso import Usuario
from app.schemas.auth import UsuarioActualizar, UsuarioCrear, UsuarioOut
from app.services import auditoria, usuarios as servicio

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


@router.get("", response_model=list[UsuarioOut])
def listar(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    _: Usuario = Depends(requiere("usuarios.gestionar")),
    db: Session = Depends(get_db),
) -> list[UsuarioOut]:
    filas = db.scalars(select(Usuario).order_by(Usuario.email).offset(skip).limit(limit))
    return [usuario_a_out(u) for u in filas]


@router.post("", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def crear(
    datos: UsuarioCrear,
    request: Request,
    actor: Usuario = Depends(requiere("usuarios.gestionar")),
    db: Session = Depends(get_db),
) -> UsuarioOut:
    try:
        usuario = servicio.crear_usuario(
            db, email=datos.email, nombre=datos.nombre, password=datos.password, rol_codigo=datos.rol,
            rama=datos.rama,
        )
    except servicio.EmailDuplicado:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un usuario con ese correo")
    except servicio.RolNoExiste:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El rol no existe")
    auditoria.registrar(
        db, accion="usuario.crear", entidad="usuario", entidad_id=str(usuario.id), usuario_id=actor.id,
        despues={"email": usuario.email, "rol": datos.rol, "rama": datos.rama}, ip=ip_cliente(request),
    )
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
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    if usuario.id == actor.id and (datos.activo is False or (datos.rol and datos.rol != usuario.rol.codigo)):
        # Evita que el único SuperAdmin se quite el acceso a sí mismo.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No puedes cambiar tu propio rol ni desactivarte")

    antes = {"nombre": usuario.nombre, "rol": usuario.rol.codigo, "activo": usuario.activo, "rama": usuario.rama}
    if datos.nombre is not None:
        usuario.nombre = datos.nombre
    if datos.rol is not None:
        try:
            usuario.rol = servicio.obtener_rol(db, datos.rol)
        except servicio.RolNoExiste:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El rol no existe")
    if datos.activo is not None:
        usuario.activo = datos.activo
    if "rama" in datos.model_fields_set:  # null quita la rama
        usuario.rama = datos.rama
    if datos.activo is False or (datos.rol is not None and datos.rol != antes["rol"]):
        servicio.revocar_sesiones(db, usuario.id)  # cierra todas sus sesiones abiertas

    auditoria.registrar(
        db, accion="usuario.actualizar", entidad="usuario", entidad_id=str(usuario.id), usuario_id=actor.id,
        antes=antes, despues={
            "nombre": usuario.nombre, "rol": usuario.rol.codigo, "activo": usuario.activo, "rama": usuario.rama,
        },
        ip=ip_cliente(request),
    )
    db.commit()
    return usuario_a_out(usuario)
