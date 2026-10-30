import uuid
from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decodificar_access_token
from app.db.session import get_db
from app.models.acceso import Usuario
from app.schemas.auth import UsuarioOut

_bearer = HTTPBearer(auto_error=False)


def _no_autenticado() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="No autenticado",
        headers={"WWW-Authenticate": "Bearer"},
    )


def ip_cliente(request: Request) -> str | None:
    return request.client.host if request.client else None


def usuario_actual(
    credenciales: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Usuario:
    if credenciales is None:
        raise _no_autenticado()
    try:
        payload = decodificar_access_token(credenciales.credentials)
        usuario_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise _no_autenticado() from None  # no se expone por qué falló el token
    usuario = db.get(Usuario, usuario_id)
    if usuario is None or not usuario.activo:
        raise _no_autenticado()
    if payload.get("cv", 0) != usuario.credenciales_version:
        raise _no_autenticado()  # token anterior a un cambio de contraseña o de rol
    return usuario


def requiere(permiso: str) -> Callable[[Usuario], Usuario]:
    """Dependencia que exige un permiso. Se verifica SIEMPRE en el servidor."""

    def _dependencia(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
        if permiso not in usuario.permisos_codigos:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permiso para esta acción")
        return usuario

    return _dependencia


def requiere_alguno(*permisos: str) -> Callable[[Usuario], Usuario]:
    """Exige al menos uno de los permisos. El servicio decide luego el alcance (todos o los propios)."""

    def _dependencia(usuario: Usuario = Depends(usuario_actual)) -> Usuario:
        if not set(permisos) & set(usuario.permisos_codigos):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tienes permiso para esta acción")
        return usuario

    return _dependencia


def usuario_a_out(usuario: Usuario) -> UsuarioOut:
    return UsuarioOut(
        id=usuario.id,
        email=usuario.email,
        nombre=usuario.nombre,
        rol=usuario.rol.codigo,
        activo=usuario.activo,
        permisos=usuario.permisos_codigos,
    )
