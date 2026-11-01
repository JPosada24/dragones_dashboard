"""Tablero del staff (GET /resumen)."""
from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.schemas.comunes import EstadoRifa, Rama


class IndicadoresOut(BaseModel):
    alumnos_activos: int
    alumnos_sin_inscripcion: int
    inscripciones_pendientes: int
    inscripciones_vencen_pronto: int
    multas_pendientes: int
    multas_saldo: int
    alertas: int


class AlertaResumenOut(BaseModel):
    tipo: Literal[
        "expulsion", "justificaciones", "vence_inscripcion", "inasistencias", "riesgo_mora", "autorizacion", "habeas",
    ]
    titulo: str
    detalle: str
    cuando: str
    ruta: str


class SesionHoyOut(BaseModel):
    id: str
    lugar: str | None
    horario: str
    cerrada: bool
    esperados: int
    presentes: int
    justificados: int
    ausentes: int
    sin_marcar: int


class RifaAnioOut(BaseModel):
    id: str
    nombre: str
    estado: EstadoRifa
    fecha_sorteo: date
    talonarios: int
    pagados: int


class CarteraOut(BaseModel):
    concepto: str
    nota: str
    monto: int


class TorneoProximoOut(BaseModel):
    id: str
    nombre: str
    rama: Rama
    fecha_inicio: date
    fecha_fin: date
    lugar: str | None
    ocupados: int
    cupo: int


class ResumenOut(BaseModel):
    indicadores: IndicadoresOut
    alertas: list[AlertaResumenOut]
    hoy: list[SesionHoyOut]
    rifas: list[RifaAnioOut]
    cartera: list[CarteraOut]
    proximo_torneo: TorneoProximoOut | None
