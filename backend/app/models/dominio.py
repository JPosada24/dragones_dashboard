"""Valores permitidos del dominio. La base de datos los refuerza con restricciones CHECK."""

RAMAS = ("masculina", "femenina")
TIPOS_DOCUMENTO = ("RC", "TI", "CC", "CE", "PA", "PPT")
TIPOS_ARCHIVO = ("identidad", "eps", "consentimiento", "certificado_medico", "foto", "otro")

ESTADOS_INSCRIPCION = ("pendiente_pago", "activo", "a_expulsar", "expulsado", "rechazado")
# Una inscripción "vigente" ocupa el cupo del alumno en ese año (solo puede haber una).
ESTADOS_VIGENTES = ("pendiente_pago", "activo", "a_expulsar")

ESTADOS_ASISTENCIA = ("presente", "ausente", "justificado")
ORIGENES_ASISTENCIA = ("propia", "grupo", "cierre", "correccion", "justificacion")
ESTADOS_JUSTIFICACION = ("pendiente", "aprobada", "rechazada")
ESTADOS_MULTA = ("pendiente", "pagada", "anulada")


def en(columna: str, valores: tuple[str, ...]) -> str:
    """Expresión SQL "columna IN ('a', 'b')" para restricciones CHECK."""
    return f"{columna} IN ({', '.join(repr(v) for v in valores)})"
