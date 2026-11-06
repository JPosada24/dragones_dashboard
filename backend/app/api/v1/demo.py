"""Datos del demo para la pantalla de entrada (sin sesión). Fuera del demo, esta ruta no existe (404)."""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.demo import CLAVE_DEMO, CUENTAS_DEMO
from app.schemas.comunes import RolCodigo

router = APIRouter(prefix="/demo", tags=["demo"])


class CuentaDemoOut(BaseModel):
    rol: RolCodigo
    email: str
    nombre: str


class DemoOut(BaseModel):
    clave: str
    cuentas: list[CuentaDemoOut]


@router.get("", response_model=DemoOut)
def demo() -> DemoOut:
    if not get_settings().demo:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No encontrado")
    return DemoOut(clave=CLAVE_DEMO,
                   cuentas=[CuentaDemoOut(rol=r, email=e, nombre=n) for r, e, n in CUENTAS_DEMO])
