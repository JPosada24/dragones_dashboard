"""Protecciones contra abuso: tamaño máximo de petición y límite de logins fallidos por IP."""
import threading
import time
from collections import defaultdict, deque
from functools import lru_cache

from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings

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
    """Cuenta fallos por clave (IP) en una ventana deslizante.

    Complementa el bloqueo por cuenta: frena a quien prueba muchas cuentas desde la misma IP.
    Vive en la memoria del proceso; cuando llegue Redis (fase posterior) se moverá allí para compartirlo.
    """

    def __init__(self, maximo: int, ventana_segundos: int) -> None:
        self.maximo = maximo
        self.ventana = ventana_segundos
        self._fallos: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _vigentes(self, clave: str, ahora: float) -> deque[float]:
        cola = self._fallos[clave]
        while cola and cola[0] <= ahora - self.ventana:
            cola.popleft()
        if not cola:
            del self._fallos[clave]  # no acumular memoria por IPs que ya no fallan
            return deque()
        return cola

    def segundos_bloqueo(self, clave: str) -> int:
        """0 si puede intentar; si no, cuántos segundos faltan para que se libere un intento."""
        with self._lock:
            ahora = time.monotonic()
            cola = self._vigentes(clave, ahora)
            if len(cola) < self.maximo:
                return 0
            return max(1, int(cola[0] + self.ventana - ahora) + 1)

    def registrar_fallo(self, clave: str) -> None:
        with self._lock:
            self._fallos[clave].append(time.monotonic())

    def reiniciar(self) -> None:
        with self._lock:
            self._fallos.clear()


@lru_cache
def limitador_sitio() -> LimitadorFallos:
    """Formularios del sitio público (sin sesión): intentos por IP y hora."""
    s = get_settings()
    return LimitadorFallos(s.sitio_envios_por_hora, 3600)


@lru_cache
def limitador_login() -> LimitadorFallos:
    s = get_settings()
    return LimitadorFallos(s.login_fallos_por_ip, s.login_ventana_minutos * 60)
