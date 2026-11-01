"""Reportes de dinero."""
from pydantic import BaseModel


class IngresoMesOut(BaseModel):
    mes: int  # 1 = enero
    inscripciones: int
    multas: int
    rifas: int
    torneos: int
    total: int


class IngresosOut(BaseModel):
    anio: int
    meses: list[IngresoMesOut]
    total: int
