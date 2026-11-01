import re
from typing import Annotated, Literal

from pydantic import AfterValidator, Field

# Valores válidos del dominio. Deben coincidir con las restricciones CHECK de la base (models/dominio.py y los
# modelos); tests/test_dominio.py lo verifica. Al estar tipados, el OpenAPI (y los tipos del frontend) los conocen.
Rama = Literal["masculina", "femenina"]
Nivel = Literal["iniciacion", "avanzado"]
TipoDocumento = Literal["RC", "TI", "CC", "CE", "PA", "PPT"]
RolCodigo = Literal["SUPERADMIN", "ADMIN", "ENTRENADOR", "MIEMBRO"]
EstadoInscripcion = Literal["pendiente_pago", "activo", "a_expulsar", "expulsado", "rechazado"]
CausaRechazo = Literal["vencimiento", "manual"]
CausaExpulsion = Literal["mora", "manual"]
EstadoAsistencia = Literal["presente", "ausente", "justificado"]
CausaCancelacion = Literal["festivo", "torneo", "horario", "manual"]
EstadoJustificacion = Literal["pendiente", "aprobada", "rechazada"]
EstadoMulta = Literal["pendiente", "pagada", "anulada"]
EstadoRifa = Literal["abierta", "sorteada", "cancelada", "eliminada"]
EstadoTorneo = Literal["programado", "cancelado", "eliminado"]
EstadoEquipo = Literal["pendiente_pago", "confirmado", "en_espera", "retirado"]
OrigenEquipo = Literal["staff", "sitio"]
EstadoCorreo = Literal["no_aplica", "pendiente", "enviado", "fallido"]

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_TELEFONO = re.compile(r"^\+?\d{7,15}$")
_DOCUMENTO = re.compile(r"^[A-Z0-9]{4,20}$")


def normalizar_email(valor: str) -> str:
    valor = valor.strip().lower()
    if len(valor) > 254 or not _EMAIL.match(valor):
        raise ValueError("Correo electrónico inválido")
    return valor


def normalizar_telefono(valor: str) -> str:
    valor = re.sub(r"[\s\-()]", "", valor)
    if not _TELEFONO.match(valor):
        raise ValueError("Teléfono inválido (7 a 15 dígitos)")
    return valor


def normalizar_documento(valor: str) -> str:
    """'1.234.567-8 ' -> '12345678'. Así el mismo documento escrito distinto no se duplica."""
    valor = re.sub(r"[\s.\-]", "", valor).upper()
    if not _DOCUMENTO.match(valor):
        raise ValueError("Número de documento inválido (4 a 20 letras o números)")
    return valor


def _vacio_a_nulo(v: str | None) -> str | None:
    return v.strip() or None if v is not None else None


# Cancelar o anular no exige explicación (quién y cuándo queda igual en la auditoría); si la escriben, se guarda.
MotivoOpcional = Annotated[str | None, Field(default=None, max_length=255), AfterValidator(_vacio_a_nulo)]
