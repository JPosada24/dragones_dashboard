from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import ip_cliente, usuario_a_out, usuario_actual
from app.core.config import get_settings
from app.core.limites import limitador_login
from app.db.session import get_db
from app.models.acceso import Usuario
from app.schemas.auth import LoginIn, TokenOut, UsuarioOut
from app.services import auth as servicio

router = APIRouter(prefix="/auth", tags=["auth"])

COOKIE_REFRESH = "refresh_token"
RUTA_COOKIE = "/api/v1/auth"


def _poner_cookie(response: Response, token: str) -> None:
    s = get_settings()
    response.set_cookie(
        COOKIE_REFRESH,
        token,
        max_age=s.refresh_token_dias * 86400,
        httponly=True,  # JavaScript no puede leerla (protege contra XSS)
        secure=s.cookie_secure,
        samesite="strict",  # no se envía desde otros sitios (protege contra CSRF)
        path=RUTA_COOKIE,  # solo viaja a las rutas de auth
    )


def _no_autorizado(detalle: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail=detalle, headers={"WWW-Authenticate": "Bearer"}
    )


@router.post("/login", response_model=TokenOut)
def login(datos: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)) -> TokenOut:
    ip = ip_cliente(request)
    limitador = limitador_login()
    espera = limitador.segundos_bloqueo(ip or "desconocida")
    if espera:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Demasiados intentos fallidos desde esta conexión. Intenta más tarde.",
            headers={"Retry-After": str(espera)},
        )
    agente = (request.headers.get("user-agent") or "")[:255] or None
    try:
        usuario = servicio.autenticar(db, datos.email, datos.password, ip)
    except servicio.ErrorAuth:
        limitador.registrar_fallo(ip or "desconocida")
        raise _no_autorizado("Credenciales inválidas")
    access, vida, refresh = servicio.emitir_sesion(db, usuario, ip, agente)
    db.commit()
    _poner_cookie(response, refresh)
    return TokenOut(access_token=access, expires_in=vida, usuario=usuario_a_out(usuario))


@router.post("/refresh", response_model=TokenOut)
def refrescar(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> TokenOut:
    if not refresh_token:
        raise _no_autorizado("Sesión expirada")
    agente = (request.headers.get("user-agent") or "")[:255] or None
    try:
        usuario, access, vida, nuevo = servicio.rotar_refresh(db, refresh_token, ip_cliente(request), agente)
    except servicio.ErrorAuth:
        response.delete_cookie(COOKIE_REFRESH, path=RUTA_COOKIE)
        raise _no_autorizado("Sesión expirada")
    _poner_cookie(response, nuevo)
    return TokenOut(access_token=access, expires_in=vida, usuario=usuario_a_out(usuario))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: Session = Depends(get_db),
) -> Response:
    if refresh_token:
        servicio.cerrar_sesion(db, refresh_token)
    response.delete_cookie(COOKIE_REFRESH, path=RUTA_COOKIE)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=UsuarioOut)
def me(usuario: Usuario = Depends(usuario_actual)) -> UsuarioOut:
    return usuario_a_out(usuario)
