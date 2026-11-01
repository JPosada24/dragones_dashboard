"""Logs, identificador por petición y reporte de errores (Sentry / GlitchTip, opcional).

- Cada petición lleva un `X-Request-ID` (el que manda Caddy o uno nuevo): sale en la respuesta y en cada línea de log,
  así un error que reporta un usuario se encuentra en los logs.
- En producción los logs son JSON (una línea por evento), fáciles de filtrar.
- Si `SENTRY_DSN` tiene valor, los errores no controlados se envían a Sentry o GlitchTip (plan gratuito). Antes de
  enviarlos se quitan cabeceras de sesión, cuerpos de las peticiones y datos del usuario: nunca salen datos personales.
"""
import contextvars
import json
import logging
import re
import uuid
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings

ID_PETICION: contextvars.ContextVar[str] = contextvars.ContextVar("id_peticion", default="-")
_ID_VALIDO = re.compile(r"^[A-Za-z0-9\-]{8,64}$")  # no se copia a los logs cualquier texto que mande el cliente
_CABECERAS_SENSIBLES = {"authorization", "cookie", "set-cookie", "x-api-key"}


class FormatoJson(logging.Formatter):
    def format(self, registro: logging.LogRecord) -> str:
        datos: dict[str, Any] = {
            "en": self.formatTime(registro, "%Y-%m-%dT%H:%M:%S%z"),
            "nivel": registro.levelname,
            "origen": registro.name,
            "mensaje": registro.getMessage(),
            "peticion": ID_PETICION.get(),
        }
        if registro.exc_info:
            datos["error"] = self.formatException(registro.exc_info)
        return json.dumps(datos, ensure_ascii=False)


class _ConPeticion(logging.Filter):
    def filter(self, registro: logging.LogRecord) -> bool:
        registro.peticion = ID_PETICION.get()
        return True


def configurar_logs() -> None:
    s = get_settings()
    manejador = logging.StreamHandler()
    manejador.addFilter(_ConPeticion())
    manejador.setFormatter(
        FormatoJson() if s.es_produccion
        else logging.Formatter("%(asctime)s %(levelname)s %(name)s [%(peticion)s]: %(message)s")
    )
    raiz = logging.getLogger()
    raiz.handlers = [manejador]
    raiz.setLevel(logging.INFO)


class IdPeticion:
    """Middleware ASGI: fija el identificador de la petición y lo devuelve en `X-Request-ID`."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        entrante = dict(scope["headers"]).get(b"x-request-id", b"").decode("latin-1")
        valor = entrante if _ID_VALIDO.fullmatch(entrante) else uuid.uuid4().hex
        token = ID_PETICION.set(valor)

        async def enviar(mensaje: Message) -> None:
            if mensaje["type"] == "http.response.start":
                mensaje.setdefault("headers", []).append((b"x-request-id", valor.encode()))
            await send(mensaje)

        try:
            await self.app(scope, receive, enviar)
        finally:
            ID_PETICION.reset(token)


def limpiar_evento(evento: dict[str, Any], _pista: dict[str, Any] | None = None) -> dict[str, Any]:
    """Antes de enviar un error a Sentry: fuera sesión, cuerpos y datos de usuario."""
    peticion = evento.get("request") or {}
    cabeceras = peticion.get("headers") or {}
    if isinstance(cabeceras, dict):
        peticion["headers"] = {
            k: ("[filtrado]" if k.lower() in _CABECERAS_SENSIBLES else v) for k, v in cabeceras.items()
        }
    for campo in ("data", "cookies", "query_string"):
        peticion.pop(campo, None)
    evento.pop("user", None)
    evento.setdefault("tags", {})["peticion"] = ID_PETICION.get()
    return evento


def iniciar_sentry() -> bool:
    s = get_settings()
    if not s.sentry_dsn:
        return False
    import sentry_sdk  # solo si se usa

    sentry_sdk.init(
        dsn=s.sentry_dsn,
        environment=s.entorno,
        send_default_pii=False,
        traces_sample_rate=0.0,  # solo errores (el plan gratuito alcanza de sobra)
        before_send=limpiar_evento,
        max_request_body_size="never",
    )
    return True
