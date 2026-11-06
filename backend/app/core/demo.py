"""Modo demo: cuentas de prueba públicas y lo que no se puede hacer en el demo.

Quien entra al demo comparte las cuentas con otros visitantes: si pudiera cambiar contraseñas o crear usuarios,
dejaría a los demás por fuera; si pudiera subir archivos, el demo serviría para alojar cualquier cosa. Todo lo demás
se puede probar y se borra en el reinicio de cada noche.
"""
import json

from starlette.types import ASGIApp, Receive, Scope, Send

CLAVE_DEMO = "DemoDragones2026"  # pública a propósito: está en la pantalla de entrada del demo
CUENTAS_DEMO = (
    ("SUPERADMIN", "superadmin@example.com", "Administrador"),
    ("ADMIN", "admin@example.com", "Daniel Mejía"),
    ("ENTRENADOR", "entrenador@example.com", "Daniel Mejía"),
)


def motivo_bloqueo(metodo: str, ruta: str, tipo_contenido: str) -> str | None:
    """Por qué el demo no permite esta petición (None = sí se permite)."""
    if metodo in ("GET", "HEAD", "OPTIONS"):
        return None
    if ruta.startswith("/api/v1/usuarios"):
        return "En el demo no se pueden cambiar las cuentas: las comparten todos los visitantes."
    if tipo_contenido.startswith("multipart/form-data"):
        return "En el demo no se suben archivos ni fotos."
    return None


class RestriccionesDemo:
    """Responde 403 a lo que el demo no permite, antes de llegar a la ruta."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            cabeceras = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
            motivo = motivo_bloqueo(scope["method"], scope["path"], cabeceras.get("content-type", ""))
            if motivo:
                cuerpo = json.dumps({"detail": motivo}).encode()
                await send({"type": "http.response.start", "status": 403, "headers": [
                    (b"content-type", b"application/json"), (b"content-length", str(len(cuerpo)).encode())]})
                await send({"type": "http.response.body", "body": cuerpo})
                return
        await self.app(scope, receive, send)
