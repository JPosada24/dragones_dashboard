"""Fechas de negocio: siempre en la zona horaria del club."""
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

ZONA_CLUB = ZoneInfo("America/Bogota")


def ahora() -> datetime:
    """Hora actual del club. Todo el código la pide por aquí (las pruebas la reemplazan para simular el reloj)."""
    return datetime.now(ZONA_CLUB)


def hoy() -> date:
    return ahora().date()


def en_zona(fecha: date, hora: time) -> datetime:
    return datetime.combine(fecha, hora, tzinfo=ZONA_CLUB)


def edad(nacimiento: date, en: date) -> int:
    return en.year - nacimiento.year - ((en.month, en.day) < (nacimiento.month, nacimiento.day))


def formato_fecha(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def formato_pesos(valor: int) -> str:
    return "$" + f"{valor:,}".replace(",", ".")
