"""Los valores válidos que publica la API (Literal) deben ser exactamente los que acepta la base (CHECK)."""
import re
from typing import get_args

import pytest
from sqlalchemy import CheckConstraint

from app.models import dominio
from app.models.notificaciones import Notificacion
from app.models.rifas import Rifa
from app.models.torneos import ESTADOS_EQUIPO, Torneo
from app.schemas import comunes


def _check(modelo: type, nombre: str) -> tuple[str, ...]:
    """Valores de un CHECK ... IN ('a', 'b') de un modelo."""
    restriccion = next(
        c for c in modelo.__table__.constraints if isinstance(c, CheckConstraint) and c.name == nombre
    )
    return tuple(re.findall(r"'([^']+)'", str(restriccion.sqltext)))


@pytest.mark.parametrize(("literal", "valores"), [
    (comunes.Rama, dominio.RAMAS),
    (comunes.Nivel, dominio.NIVELES),
    (comunes.TipoDocumento, dominio.TIPOS_DOCUMENTO),
    (comunes.EstadoInscripcion, dominio.ESTADOS_INSCRIPCION),
    (comunes.EstadoAsistencia, dominio.ESTADOS_ASISTENCIA),
    (comunes.CausaCancelacion, dominio.CAUSAS_CANCELACION),
    (comunes.EstadoJustificacion, dominio.ESTADOS_JUSTIFICACION),
    (comunes.EstadoMulta, dominio.ESTADOS_MULTA),
    (comunes.EstadoEquipo, ESTADOS_EQUIPO),
])
def test_literal_igual_al_dominio(literal, valores):
    assert set(get_args(literal)) == set(valores)


@pytest.mark.parametrize(("literal", "modelo", "restriccion"), [
    (comunes.EstadoRifa, Rifa, "ck_rifas_estado"),
    (comunes.EstadoTorneo, Torneo, "ck_torneos_estado"),
    (comunes.EstadoCorreo, Notificacion, "ck_notif_email"),
])
def test_literal_igual_al_check_de_la_tabla(literal, modelo, restriccion):
    assert set(get_args(literal)) == set(_check(modelo, restriccion))


def test_roles_iguales_al_catalogo():
    from app.core.permissions import ROLES

    assert set(get_args(comunes.RolCodigo)) == set(ROLES)
