"""Salud del sistema, para el healthcheck de Docker y el monitor de disponibilidad externo. Sin datos sensibles."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(tags=["sistema"])

# El worker deja su latido cada ~15 s; si pasan 10 minutos sin latido, algo lo detuvo.
WORKER_SIN_LATIDO_SEGUNDOS = 600


@router.get("/salud")
def salud(db: Session = Depends(get_db)) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        raise HTTPException(status_code=503, detail="Base de datos no disponible") from e
    return {"estado": "ok"}


@router.get("/salud/worker")
def salud_worker(db: Session = Depends(get_db)) -> dict[str, str | int]:
    """503 si el worker no corre: sin él no se cierra la asistencia, no vencen inscripciones ni salen correos."""
    segundos = db.scalar(
        text("SELECT EXTRACT(EPOCH FROM now() - en)::int FROM latidos WHERE servicio = 'worker'")
    )
    if segundos is None or segundos > WORKER_SIN_LATIDO_SEGUNDOS:
        raise HTTPException(status_code=503, detail="El worker no está corriendo")
    return {"estado": "ok", "ultimo_latido_hace_s": segundos}


# Los monitores externos (UptimeRobot) revisan con HEAD; solo con GET respondían 405 y daban "caído".
# Fuera del esquema: es el mismo contrato que el GET.
router.add_api_route("/salud", salud, methods=["HEAD"], include_in_schema=False)
router.add_api_route("/salud/worker", salud_worker, methods=["HEAD"], include_in_schema=False)
