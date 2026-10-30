from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import get_settings
from app.core.limites import LimiteCuerpo
from app.services.errores import ErrorNegocio


def crear_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="Dragones API",
        version="0.1.0",
        # La documentación interactiva solo existe en desarrollo.
        docs_url=None if s.es_produccion else "/api/docs",
        redoc_url=None,
        openapi_url=None if s.es_produccion else "/api/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_lista,  # lista explícita, nunca "*"
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    # Tope de tamaño antes que nada: una petición gigante no llega a leerse entera.
    app.add_middleware(LimiteCuerpo, max_bytes=s.max_cuerpo_mb * 1024 * 1024)

    @app.middleware("http")
    async def cabeceras_de_seguridad(request: Request, call_next):
        respuesta = await call_next(request)
        respuesta.headers["X-Content-Type-Options"] = "nosniff"
        respuesta.headers["X-Frame-Options"] = "DENY"
        respuesta.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api/v1/auth"):
            respuesta.headers["Cache-Control"] = "no-store"
        return respuesta

    @app.exception_handler(ErrorNegocio)
    async def error_de_negocio(request: Request, exc: ErrorNegocio) -> JSONResponse:
        # Regla de negocio incumplida: el mensaje está escrito para el usuario final.
        return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})

    app.include_router(api_router, prefix="/api/v1")
    return app


app = crear_app()
