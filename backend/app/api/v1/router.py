from fastapi import APIRouter

from app.api.v1 import acudientes, alumnos, auth, configuracion, inscripciones, salud, usuarios

api_router = APIRouter()
api_router.include_router(salud.router)
api_router.include_router(auth.router)
api_router.include_router(usuarios.router)
api_router.include_router(configuracion.router)
api_router.include_router(alumnos.router)
api_router.include_router(acudientes.router)
api_router.include_router(inscripciones.router)
