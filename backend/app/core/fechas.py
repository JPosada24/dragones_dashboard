"""Fechas de negocio: siempre en la zona horaria del club."""
import calendar
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


def sumar_meses(d: date, meses: int) -> date:
    """31/01 + 1 mes = 28/02 (o 29): si el día no existe en el mes destino, se usa el último."""
    total = d.month - 1 + meses
    anio, mes = d.year + total // 12, total % 12 + 1
    return date(anio, mes, min(d.day, calendar.monthrange(anio, mes)[1]))


def edad(nacimiento: date, en: date) -> int:
    return en.year - nacimiento.year - ((en.month, en.day) < (nacimiento.month, nacimiento.day))


def formato_fecha(d: date) -> str:
    return d.strftime("%d/%m/%Y")


def formato_pesos(valor: int) -> str:
    return "$" + f"{valor:,}".replace(",", ".")
