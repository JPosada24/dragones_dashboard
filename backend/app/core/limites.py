"""Protecciones contra abuso: tamaño máximo de petición y límite de intentos por IP (login y sitio público)."""
import hashlib
from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings
from app.db.session import engine

MENSAJE_CUERPO = "La petición supera el tamaño máximo permitido."


class LimiteCuerpo:
    """Rechaza con 413 las peticiones más grandes que el máximo, antes de que se guarden en memoria o disco.

    Mira Content-Length y, por si viene "chunked" o miente, también cuenta los bytes mientras llegan.
    """

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        largo = dict(scope["headers"]).get(b"content-length")
        if largo is not None and (not largo.isdigit() or int(largo) > self.max_bytes):
            await JSONResponse({"detail": MENSAJE_CUERPO}, status_code=413)(scope, receive, send)
            return

        recibidos = 0

        async def receive_limitado() -> Message:
            nonlocal recibidos
            mensaje = await receive()
            if mensaje["type"] == "http.request":
                recibidos += len(mensaje.get("body", b""))
                if recibidos > self.max_bytes:
                    raise HTTPException(status_code=413, detail=MENSAJE_CUERPO)
            return mensaje

        await self.app(scope, receive_limitado, send)


class LimitadorFallos:
    """Cuenta intentos por clave (IP) en una ventana deslizante, en Postgres.

    Complementa el bloqueo por cuenta: frena a quien prueba muchas cuentas desde la misma IP. Vive en la base para
    que todos los procesos de la API compartan la cuenta (en memoria, cada proceso contaba por su lado). Usa su propia
    conexión: un fallo se registra aunque la petición termine en error y su transacción se deshaga.
    La IP no se guarda en claro: solo su SHA-256. El worker borra lo de más de un día.
    """

    def __init__(self, ambito: str, maximo: int, ventana_segundos: int) -> None:
        self.ambito = ambito
        self.maximo = maximo
        self.ventana = ventana_segundos

    @staticmethod
    def _huella(clave: str) -> str:
        return hashlib.sha256(clave.encode("utf-8")).hexdigest()

    def segundos_bloqueo(self, clave: str) -> int:
        """0 si puede intentar; si no, cuántos segundos faltan para que se libere un intento."""
        with engine.connect() as conn:
            cuantos, faltan = conn.execute(
                text(
                    "SELECT count(*), EXTRACT(EPOCH FROM min(creado_en) + make_interval(secs => :ventana) - now())"
                    " FROM intentos WHERE ambito = :ambito AND clave = :clave"
                    " AND creado_en > now() - make_interval(secs => :ventana)"
                ),
                {"ambito": self.ambito, "clave": self._huella(clave), "ventana": self.ventana},
            ).one()
        if cuantos < self.maximo:
            return 0
        return max(1, int(faltan) + 1)

    def registrar_fallo(self, clave: str) -> None:
        with engine.begin() as conn:
            conn.execute(
                text("INSERT INTO intentos (ambito, clave) VALUES (:ambito, :clave)"),
                {"ambito": self.ambito, "clave": self._huella(clave)},
            )

    def reiniciar(self) -> None:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM intentos WHERE ambito = :ambito"), {"ambito": self.ambito})


def purgar_intentos(db: Session) -> str:
    """Tarea del worker: los intentos de más de un día ya no cuentan para ninguna ventana."""
    borrados = db.execute(text("DELETE FROM intentos WHERE creado_en < now() - interval '1 day'")).rowcount
    return f"{borrados} intentos viejos borrados"


@lru_cache
def limitador_sitio() -> LimitadorFallos:
    """Formularios del sitio público (sin sesión): intentos por IP y hora."""
    s = get_settings()
    return LimitadorFallos("sitio", s.sitio_envios_por_hora, 3600)


@lru_cache
def limitador_login() -> LimitadorFallos:
    s = get_settings()
    return LimitadorFallos("login", s.login_fallos_por_ip, s.login_ventana_minutos * 60)
