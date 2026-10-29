import uuid
from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import requiere_alguno
from app.db.session import get_db
from app.models.acceso import Usuario
from app.services import mora as servicio

router = APIRouter(prefix="/mora", tags=["mora"])


class DeudaOut(BaseModel):
    concepto: str
    monto: int
    vence: date


class SituacionOut(BaseModel):
    alumno_id: uuid.UUID
    alumno_nombre: str
    rama: str
    total_vencido: int
    vencida_desde: date
    entra_en_mora: date
    en_mora: bool
    deudas: list[DeudaOut]


@router.get("", response_model=list[SituacionOut])
def en_riesgo(
    usuario: Usuario = Depends(requiere_alguno("alumnos.ver_todos", "alumnos.ver_rama")),
    db: Session = Depends(get_db),
) -> list[SituacionOut]:
    """Alumnos con deuda vencida (multas, talonarios): cuánto deben, desde cuándo y si ya están en mora."""
    return [
        SituacionOut(
            alumno_id=s.alumno.id, alumno_nombre=f"{s.alumno.nombres} {s.alumno.apellidos}", rama=s.alumno.rama,
            total_vencido=s.total_vencido, vencida_desde=s.vencida_desde, entra_en_mora=s.entra_en_mora,
            en_mora=s.en_mora, deudas=[DeudaOut(concepto=d.concepto, monto=d.monto, vence=d.vence) for d in s.deudas],
        )
        for s in servicio.listar_en_riesgo(db, usuario)
    ]
