"""Fechas de negocio: siempre en la zona horaria del club."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

ZONA_CLUB = ZoneInfo("America/Bogota")


def hoy() -> date:
    return datetime.now(ZONA_CLUB).date()


def edad(nacimiento: date, en: date) -> int:
    return en.year - nacimiento.year - ((en.month, en.day) < (nacimiento.month, nacimiento.day))


def formato_fecha(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def formato_pesos(valor: int) -> str:
    return "$" + f"{valor:,}".replace(",", ".")
