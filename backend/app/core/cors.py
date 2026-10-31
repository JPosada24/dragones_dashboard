"""CORS del sitio público: sus orígenes solo pueden usar /api/v1/publico, y nunca con credenciales.

El CORS general (CORS_ORIGINS) es para el panel y permite credenciales (la cookie de sesión). El sitio público
vive en otro dominio y no las necesita: así, aunque alguien inyectara código en el sitio, no podría actuar con
la sesión de un usuario del panel.
"""
from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

PREFIJO = "/api/v1/publico/"


class CorsSitio:
    def __init__(self, app: ASGIApp, origenes: list[str]) -> None:
        self.app = app
        self.origenes = set(origenes)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        origen = Headers(scope=scope).get("origin") if scope["type"] == "http" else None
        if origen is None or origen not in self.origenes or not scope["path"].startswith(PREFIJO):
            await self.app(scope, receive, send)
            return

        if scope["method"] == "OPTIONS":  # preflight: solo GET/POST y Content-Type
            respuesta = Response(status_code=204, headers={
                "Access-Control-Allow-Origin": origen,
                "Access-Control-Allow-Methods": "GET, POST",
                "Access-Control-Allow-Headers": "Content-Type",
                "Access-Control-Max-Age": "600",
                "Vary": "Origin",
            })
            await respuesta(scope, receive, send)
            return

        async def enviar(mensaje: Message) -> None:
            if mensaje["type"] == "http.response.start":
                cabeceras = MutableHeaders(scope=mensaje)
                cabeceras["Access-Control-Allow-Origin"] = origen
                cabeceras.append("Vary", "Origin")
            await send(mensaje)

        await self.app(scope, receive, enviar)
