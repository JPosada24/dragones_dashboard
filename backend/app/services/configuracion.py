import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.sistema import Configuracion
from app.services import auditoria

# clave -> (valor por defecto, descripción). El tipo del valor por defecto fija el tipo permitido.
DEFAULTS: dict[str, tuple[Any, str]] = {
    "multa_inasistencia": (2000, "Valor de la multa por inasistencia (COP)"),
    "plazo_pago_dias": (30, "Días máximos para pagar la inscripción"),
    "valor_inscripcion": (90000, "Valor de la inscripción anual (COP)"),
    "edad_mayoria": (18, "Edad desde la que el alumno no necesita acudiente"),
    "documento_max_mb": (5, "Tamaño máximo de cada documento subido (MB)"),
    "meses_mora_expulsion": (3, "Meses con una deuda sin pagar (multas, rifas) antes de marcar 'A expulsar'"),
    "expulsion_automatica": (False, "Expulsar automáticamente (false = requiere confirmación)"),
    "dias_aviso_mora": (15, "Días antes de entrar en mora en que se avisa a la familia"),
    "hora_cierre_asistencia": ("23:59", "Hora de cierre diario de la asistencia (HH:MM)"),
    "minutos_marcar_antes": (30, "Minutos antes del inicio desde los que el alumno puede marcar su asistencia"),
    "dias_para_justificar": (3, "Días después de la sesión para enviar una justificación"),
    "inasistencias_consecutivas_aviso": (4, "Inasistencias seguidas que avisan al staff"),
    "recordatorios_dias_antes": ([7, 1], "Días antes del vencimiento en que se envía recordatorio"),
    "rifas_por_anio": (4, "Cantidad de rifas por año"),
    "puestos_por_talonario": (20, "Puestos por talonario de rifa"),
    "precio_puesto": (2000, "Precio de cada puesto de rifa (COP)"),
    "cupo_equipos_sugerido": (18, "Cupo sugerido de equipos por rama en un torneo"),
}


class ConfigInvalida(ValueError):
    pass


def validar_valor(clave: str, valor: Any) -> Any:
    if clave not in DEFAULTS:
        raise ConfigInvalida(f"Parámetro desconocido: {clave}")
    modelo = DEFAULTS[clave][0]
    if isinstance(modelo, bool):
        if not isinstance(valor, bool):
            raise ConfigInvalida("Debe ser verdadero o falso")
    elif isinstance(modelo, int):
        if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0 or valor > 10_000_000:
            raise ConfigInvalida("Debe ser un entero entre 0 y 10.000.000")
    elif isinstance(modelo, str):
        if not isinstance(valor, str) or not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", valor):
            raise ConfigInvalida("Debe ser una hora en formato HH:MM")
    elif isinstance(modelo, list):
        ok = isinstance(valor, list) and len(valor) <= 10 and all(
            isinstance(x, int) and not isinstance(x, bool) and 0 <= x <= 365 for x in valor
        )
        if not ok:
            raise ConfigInvalida("Debe ser una lista de enteros entre 0 y 365")
    return valor


def obtener(db: Session, clave: str) -> Any:
    """Valor vigente de un parámetro (el de la tabla; si aún no se sembró, el valor por defecto)."""
    fila = db.get(Configuracion, clave)
    return fila.valor if fila is not None else DEFAULTS[clave][0]


def listar(db: Session) -> list[Configuracion]:
    return list(db.scalars(select(Configuracion).order_by(Configuracion.clave)))


def actualizar(
    db: Session, *, clave: str, valor: Any, usuario_id: uuid.UUID, ip: str | None
) -> Configuracion:
    valor = validar_valor(clave, valor)
    fila = db.get(Configuracion, clave)
    if fila is None:
        raise ConfigInvalida(f"Parámetro desconocido: {clave}")
    antes = fila.valor
    fila.valor = valor
    fila.actualizado_por = usuario_id
    auditoria.registrar(
        db, accion="config.actualizar", entidad="configuracion", entidad_id=clave,
        usuario_id=usuario_id, antes={"valor": antes}, despues={"valor": valor}, ip=ip,
    )
    db.commit()
    return fila
