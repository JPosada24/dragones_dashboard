import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import ip_cliente, requiere, usuario_a_out
from app.core.security import hash_password
from app.db.session import get_db
from app.models.acceso import Usuario
from app.models.alumnos import Acudiente, Alumno
from app.schemas.auth import UsuarioActualizar, UsuarioCrear, UsuarioListaOut, UsuarioOut
from app.services import alumnos, auditoria
from app.services import usuarios as servicio
from app.services.errores import Conflicto, ErrorNegocio, NoEncontrado

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


def _vinculos(db: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """A quién pertenece cada cuenta de Miembro (alumno mayor o acudiente)."""
    vinculos: dict[uuid.UUID, str] = {}
    for a in db.scalars(select(Alumno).where(Alumno.usuario_id.in_(ids))):
        vinculos[a.usuario_id] = f"Alumno {a.codigo} · {a.nombres} {a.apellidos}"
    for ac in db.scalars(select(Acudiente).where(Acudiente.usuario_id.in_(ids))):
        hijos = db.scalars(select(Alumno).where(Alumno.vinculos.any(acudiente_id=ac.id))).all()
        nombres = ", ".join(f"{h.codigo} {h.nombres}" for h in hijos) or "sin alumnos"
        vinculos[ac.usuario_id] = f"Acudiente de {nombres}"
    return vinculos


@router.get("", response_model=list[UsuarioListaOut])
def listar(
    skip: int = Query(0, ge=0),
    limit: int = Query(200, ge=1, le=500),
    _: Usuario = Depends(requiere("usuarios.gestionar")),
    db: Session = Depends(get_db),
) -> list[UsuarioListaOut]:
    filas = list(db.scalars(select(Usuario).order_by(Usuario.nombre).offset(skip).limit(limit)))
    vinculos = _vinculos(db, [u.id for u in filas])
    return [UsuarioListaOut(**usuario_a_out(u).model_dump(), vinculado_a=vinculos.get(u.id)) for u in filas]


def _vincular(db: Session, usuario: Usuario, datos: UsuarioCrear) -> str | None:
    """Une la cuenta de un Miembro con el alumno (mayor de edad) o el acudiente al que pertenece."""
    if not (datos.vincular_alumno_id or datos.vincular_acudiente_id):
        return None
    if datos.rol != "MIEMBRO":
        raise ErrorNegocio("Solo las cuentas de Miembro se vinculan a un alumno o acudiente.")
    if datos.vincular_alumno_id:
        destino = db.get(Alumno, datos.vincular_alumno_id)
        if destino is None:
            raise NoEncontrado("Alumno no encontrado.")
        if alumnos.es_menor(db, destino.fecha_nacimiento):
            raise ErrorNegocio("Un menor de edad no tiene cuenta propia: crea la cuenta para su acudiente.")
    else:
        destino = db.get(Acudiente, datos.vincular_acudiente_id)
        if destino is None:
            raise NoEncontrado("Acudiente no encontrado.")
    if destino.usuario_id is not None:
        raise Conflicto("Ese alumno o acudiente ya tiene una cuenta.")
    destino.usuario_id = usuario.id
    return f"{'alumno' if isinstance(destino, Alumno) else 'acudiente'}:{destino.id}"


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
        )
    except servicio.EmailDuplicado:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un usuario con ese correo") from None
    except servicio.RolNoExiste:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "El rol no existe") from None
    auditoria.registrar(
        db, accion="usuario.crear", entidad="usuario", entidad_id=str(usuario.id), usuario_id=actor.id,
        despues={
            "email": usuario.email, "rol": datos.rol, "vinculo": _vincular(db, usuario, datos),
        },
        ip=ip_cliente(request),
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

    antes = {"nombre": usuario.nombre, "rol": usuario.rol.codigo, "activo": usuario.activo}
    if datos.nombre is not None:
        usuario.nombre = datos.nombre
    if datos.rol is not None:
        try:
            usuario.rol = servicio.obtener_rol(db, datos.rol)
        except servicio.RolNoExiste:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "El rol no existe") from None
    if datos.activo is not None:
        usuario.activo = datos.activo
    if datos.password is not None:
        usuario.password_hash = hash_password(datos.password)
    cambio_credenciales = datos.password is not None or (datos.rol is not None and datos.rol != antes["rol"])
    if cambio_credenciales:
        usuario.credenciales_version += 1  # los tokens anteriores dejan de valer de inmediato
    if datos.activo is False or cambio_credenciales:
        servicio.revocar_sesiones(db, usuario.id)  # cierra todas sus sesiones abiertas

    auditoria.registrar(
        db, accion="usuario.actualizar", entidad="usuario", entidad_id=str(usuario.id), usuario_id=actor.id,
        antes=antes, despues={
            "nombre": usuario.nombre, "rol": usuario.rol.codigo, "activo": usuario.activo,
            "password_cambiada": datos.password is not None,  # nunca la contraseña
        },
        ip=ip_cliente(request),
    )
    db.commit()
    return usuario_a_out(usuario)
