"""Festivos de Colombia (Ley 51 de 1983, "Ley Emiliani"), calculados para cualquier año.

- Fijos: no se mueven.
- Emiliani: si no caen en lunes, pasan al lunes siguiente.
- Religiosos móviles: dependen del Domingo de Pascua; Jueves y Viernes Santo no se mueven, los demás
  ya caen (o se trasladan) en lunes.
"""
from datetime import date, timedelta
from functools import lru_cache

_FIJOS = [
    (1, 1, "Año Nuevo"),
    (5, 1, "Día del Trabajo"),
    (7, 20, "Día de la Independencia"),
    (8, 7, "Batalla de Boyacá"),
    (12, 8, "Inmaculada Concepción"),
    (12, 25, "Navidad"),
]

_EMILIANI = [
    (1, 6, "Reyes Magos"),
    (3, 19, "San José"),
    (6, 29, "San Pedro y San Pablo"),
    (8, 15, "Asunción de la Virgen"),
    (10, 12, "Día de la Raza"),
    (11, 1, "Todos los Santos"),
    (11, 11, "Independencia de Cartagena"),
]

# Días desde el Domingo de Pascua (ya trasladados al lunes cuando aplica).
_PASCUA = [
    (-3, "Jueves Santo"),
    (-2, "Viernes Santo"),
    (43, "Ascensión del Señor"),
    (64, "Corpus Christi"),
    (71, "Sagrado Corazón"),
]


def domingo_de_pascua(anio: int) -> date:
    """Algoritmo anónimo gregoriano (Meeus/Jones/Butcher)."""
    a, b, c = anio % 19, anio // 100, anio % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    mes = (h + l_ - 7 * m + 114) // 31
    dia = (h + l_ - 7 * m + 114) % 31 + 1
    return date(anio, mes, dia)


def _al_lunes(d: date) -> date:
    return d + timedelta(days=(7 - d.weekday()) % 7)


@lru_cache(maxsize=32)
def festivos(anio: int) -> dict[date, str]:
    resultado = {date(anio, m, d): nombre for m, d, nombre in _FIJOS}
    resultado.update({_al_lunes(date(anio, m, d)): nombre for m, d, nombre in _EMILIANI})
    pascua = domingo_de_pascua(anio)
    resultado.update({pascua + timedelta(days=n): nombre for n, nombre in _PASCUA})
    return resultado


def festivo(d: date) -> str | None:
    """Nombre del festivo si `d` lo es; None si no."""
    return festivos(d.year).get(d)
