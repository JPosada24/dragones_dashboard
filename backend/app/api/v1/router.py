from fastapi import APIRouter

from app.api.v1 import (
    acudientes, alumnos, auth, configuracion, inscripciones, justificaciones, multas, notificaciones, rifas, salud,
    sesiones, torneos, usuarios,
)

api_router = APIRouter()
api_router.include_router(salud.router)
api_router.include_router(auth.router)
api_router.include_router(usuarios.router)
api_router.include_router(configuracion.router)
api_router.include_router(alumnos.router)
api_router.include_router(acudientes.router)
api_router.include_router(inscripciones.router)
api_router.include_router(sesiones.router)
api_router.include_router(justificaciones.router)
api_router.include_router(multas.router)
api_router.include_router(rifas.router)
api_router.include_router(torneos.router)
api_router.include_router(notificaciones.router)
