"""Alumnos y acudientes: alta, edición, vínculos y qué alumnos puede ver cada rol."""
import uuid
from datetime import date
from typing import Any, get_args

from sqlalchemy import ColumnElement, Integer, cast, false, func, or_, select, true
from sqlalchemy.orm import Session

from app.core import cifrado
from app.core.fechas import edad, hoy
from app.models.acceso import Usuario
from app.models.alumnos import Acudiente, Alumno, AlumnoAcudiente, Inscripcion
from app.models.dominio import ESTADOS_VIGENTES
from app.schemas.comunes import TipoDocumento, normalizar_documento
from app.services import auditoria, configuracion
from app.services.errores import Conflicto, ErrorNegocio, NoEncontrado, Prohibido

MENOR_SIN_ACUDIENTE = "El alumno es menor de edad: debe tener al menos un acudiente."


def enmascarar(ultimos: str) -> str:
    return f"****{ultimos}"


def es_menor(db: Session, fecha_nacimiento: date, en: date | None = None) -> bool:
    return edad(fecha_nacimiento, en or hoy()) < configuracion.obtener(db, "edad_mayoria")


def _campos_documento(tipo: str, numero: str) -> dict[str, Any]:
    return {
        "tipo_documento": tipo,
        "documento_cifrado": cifrado.cifrar(numero),
        "documento_indice": cifrado.indice_ciego(f"{tipo}:{numero}"),
        "documento_ultimos": numero[-4:],
    }


def _aplicar_documento(cambios: dict[str, Any], actual: Alumno | Acudiente | None = None) -> None:
    """Convierte tipo/número en sus columnas cifradas. En una edición, completa con el valor actual."""
    numero = cambios.pop("documento", None)
    tipo = cambios.pop("tipo_documento", None)
    if numero is None and tipo is None:
        return
    if actual is not None:
        tipo = tipo or actual.tipo_documento
        numero = numero or cifrado.descifrar(actual.documento_cifrado)
    cambios.update(_campos_documento(tipo, numero))


def _verificar_documento_libre(db: Session, modelo: type[Alumno] | type[Acudiente], cambios: dict, propio=None):
    if "documento_indice" not in cambios:
        return
    q = select(modelo.id).where(modelo.documento_indice == cambios["documento_indice"])
    if propio is not None:
        q = q.where(modelo.id != propio)
    if db.scalar(q) is not None:
        quien = "alumno" if modelo is Alumno else "acudiente"
        raise Conflicto(f"Ya existe un {quien} con ese documento.")


def _verificar_usuario(db: Session, modelo: type[Alumno] | type[Acudiente], cambios: dict, propio=None):
    usuario_id = cambios.get("usuario_id")
    if usuario_id is None:
        return
    if db.get(Usuario, usuario_id) is None:
        raise ErrorNegocio("El usuario indicado no existe.")
    q = select(modelo.id).where(modelo.usuario_id == usuario_id)
    if propio is not None:
        q = q.where(modelo.id != propio)
    if db.scalar(q) is not None:
        quien = "alumno" if modelo is Alumno else "acudiente"
        raise Conflicto(f"Ese usuario ya está asociado a otro {quien}.")


def _verificar_rama_permitida(actor: Usuario, rama: str) -> None:
    """Quien no ve todos los alumnos (el Entrenador) solo registra o mueve alumnos dentro de su rama."""
    if "alumnos.ver_todos" in actor.permisos_codigos or rama == actor.rama:
        return
    if actor.rama is None:
        raise Prohibido("No tienes una rama asignada: pide al SuperAdmin que te asigne una.")
    raise Prohibido(f"Solo puedes registrar alumnos de tu rama ({actor.rama}).")


def _resumen_alumno(a: Alumno) -> dict[str, Any]:
    """Foto del alumno para la auditoría. El documento va enmascarado: nunca en claro en la bitácora."""
    return {
        "codigo": a.codigo, "nombres": a.nombres, "apellidos": a.apellidos, "tipo_documento": a.tipo_documento,
        "documento": enmascarar(a.documento_ultimos), "fecha_nacimiento": a.fecha_nacimiento.isoformat(),
        "rama": a.rama, "telefono": a.telefono, "email": a.email, "direccion": a.direccion, "eps": a.eps,
        "usuario_id": str(a.usuario_id) if a.usuario_id else None, "activo": a.activo,
    }


def _resumen_acudiente(a: Acudiente) -> dict[str, Any]:
    return {
        "nombres": a.nombres, "apellidos": a.apellidos, "tipo_documento": a.tipo_documento,
        "documento": enmascarar(a.documento_ultimos), "telefono": a.telefono, "email": a.email,
        "usuario_id": str(a.usuario_id) if a.usuario_id else None,
    }


# ---------- Visibilidad ----------
def filtro_propios(usuario: Usuario) -> ColumnElement[bool]:
    """El propio alumno (mayor de edad con cuenta) o los alumnos de los que el usuario es acudiente."""
    hijos = select(AlumnoAcudiente.alumno_id).join(Acudiente).where(Acudiente.usuario_id == usuario.id)
    return or_(Alumno.usuario_id == usuario.id, Alumno.id.in_(hijos))


def filtro_visibles(usuario: Usuario) -> ColumnElement[bool]:
    permisos = set(usuario.permisos_codigos)
    if "alumnos.ver_todos" in permisos:
        return true()
    condiciones = []
    if "alumnos.ver_rama" in permisos and usuario.rama:
        condiciones.append(Alumno.rama == usuario.rama)
    if "alumnos.ver_propios" in permisos:
        condiciones.append(filtro_propios(usuario))
    return or_(*condiciones) if condiciones else false()


def obtener_visible(db: Session, usuario: Usuario, alumno_id: uuid.UUID) -> Alumno:
    alumno = db.scalar(select(Alumno).where(Alumno.id == alumno_id, filtro_visibles(usuario)))
    if alumno is None:
        # Mismo mensaje si no existe o si no le corresponde: no se revela qué alumnos hay.
        raise NoEncontrado("Alumno no encontrado.")
    return alumno


def obtener_por_id(db: Session, alumno_id: uuid.UUID) -> Alumno:
    """Sin filtro de visibilidad: solo para datos ya públicos dentro del club (p. ej. el ganador de una rifa)."""
    alumno = db.get(Alumno, alumno_id)
    if alumno is None:
        raise NoEncontrado("Alumno no encontrado.")
    return alumno


def es_propio(db: Session, usuario: Usuario, alumno_id: uuid.UUID) -> bool:
    return db.scalar(select(Alumno.id).where(Alumno.id == alumno_id, filtro_propios(usuario))) is not None


def _indices_documento(texto: str) -> list[str]:
    """Índices ciegos del texto como número de documento completo, en cada tipo (búsqueda exacta, nunca parcial)."""
    try:
        numero = normalizar_documento(texto)
    except ValueError:
        return []
    return [cifrado.indice_ciego(f"{tipo}:{numero}") for tipo in get_args(TipoDocumento)]


def listar(
    db: Session, usuario: Usuario, *, rama: str | None, buscar: str | None, activo: bool | None = None,
    skip: int, limit: int,
) -> list[Alumno]:
    q = select(Alumno).where(filtro_visibles(usuario))
    if rama:
        q = q.where(Alumno.rama == rama)
    if activo is not None:
        q = q.where(Alumno.activo.is_(activo))
    if buscar:
        condiciones = [
            Alumno.nombres.icontains(buscar, autoescape=True), Alumno.apellidos.icontains(buscar, autoescape=True),
            Alumno.codigo == buscar.strip().upper(),
        ]
        if indices := _indices_documento(buscar):
            condiciones.append(Alumno.documento_indice.in_(indices))
        q = q.where(or_(*condiciones))
    return list(db.scalars(q.order_by(Alumno.apellidos, Alumno.nombres).offset(skip).limit(limit)))


def estados_inscripcion(db: Session, alumno_ids: list[uuid.UUID], anio: int) -> dict[uuid.UUID, str]:
    """Estado de la inscripción de cada alumno en el año: la vigente si la hay; si no, la más reciente."""
    if not alumno_ids:
        return {}
    filas = db.execute(
        select(Inscripcion.alumno_id, Inscripcion.estado)
        .where(Inscripcion.alumno_id.in_(alumno_ids), Inscripcion.anio == anio)
        .order_by(Inscripcion.creado_en)
    ).all()
    estados: dict[uuid.UUID, str] = {}
    for alumno_id, estado in filas:
        if estados.get(alumno_id) not in ESTADOS_VIGENTES:
            estados[alumno_id] = estado
    return estados


# ---------- Alumnos ----------
def _vincular(db: Session, alumno: Alumno, *, acudiente_id: uuid.UUID, parentesco: str, principal: bool) -> None:
    acudiente = db.get(Acudiente, acudiente_id)
    if acudiente is None:
        raise NoEncontrado("Acudiente no encontrado.")
    if any(v.acudiente.id == acudiente_id for v in alumno.vinculos):
        raise Conflicto("Ese acudiente ya está vinculado al alumno.")
    if principal or not alumno.vinculos:  # el primero siempre es el principal
        for v in alumno.vinculos:
            v.principal = False
        principal = True
    alumno.vinculos.append(AlumnoAcudiente(acudiente=acudiente, parentesco=parentesco, principal=principal))


# Candado de la transacción para asignar códigos: dos altas a la vez no reciben el mismo consecutivo.
_CANDADO_CODIGOS = 7311


def siguiente_codigo(db: Session, rama: str) -> str:
    """El consecutivo siguiente de la rama: F001, F002… o M001… (nunca se reutiliza uno ya dado)."""
    db.execute(select(func.pg_advisory_xact_lock(_CANDADO_CODIGOS)))
    letra = "F" if rama == "femenina" else "M"
    ultimo = db.scalar(
        select(func.max(cast(func.substr(Alumno.codigo, 2), Integer))).where(Alumno.codigo.like(f"{letra}%"))
    )
    return f"{letra}{(ultimo or 0) + 1:03d}"


def crear_alumno(
    db: Session, *, datos: dict[str, Any], vinculos: list[dict[str, Any]], actor: Usuario, ip: str | None
) -> Alumno:
    _verificar_rama_permitida(actor, datos["rama"])
    _aplicar_documento(datos)
    _verificar_documento_libre(db, Alumno, datos)
    _verificar_usuario(db, Alumno, datos)
    alumno = Alumno(**datos, codigo=siguiente_codigo(db, datos["rama"]))
    db.add(alumno)
    for v in vinculos:
        _vincular(db, alumno, **v)
    if es_menor(db, alumno.fecha_nacimiento) and not alumno.vinculos:
        raise ErrorNegocio(MENOR_SIN_ACUDIENTE)
    db.flush()
    auditoria.registrar(
        db, accion="alumno.crear", entidad="alumno", entidad_id=str(alumno.id), usuario_id=actor.id,
        despues={**_resumen_alumno(alumno), "acudientes": [str(v.acudiente_id) for v in alumno.vinculos]}, ip=ip,
    )
    return alumno


def actualizar_alumno(
    db: Session, alumno: Alumno, *, cambios: dict[str, Any], actor: Usuario, ip: str | None
) -> Alumno:
    antes = _resumen_alumno(alumno)
    if "rama" in cambios:
        _verificar_rama_permitida(actor, cambios["rama"])
    _aplicar_documento(cambios, alumno)
    _verificar_documento_libre(db, Alumno, cambios, alumno.id)
    _verificar_usuario(db, Alumno, cambios, alumno.id)
    if "rama" in cambios and cambios["rama"] != alumno.rama:
        # Al corregir la rama recibe un código de la otra (los talonarios ya entregados conservan el suyo).
        cambios["codigo"] = siguiente_codigo(db, cambios["rama"])
    for campo, valor in cambios.items():
        setattr(alumno, campo, valor)
    if es_menor(db, alumno.fecha_nacimiento) and not alumno.vinculos:
        raise ErrorNegocio(MENOR_SIN_ACUDIENTE)
    db.flush()
    auditoria.registrar(
        db, accion="alumno.actualizar", entidad="alumno", entidad_id=str(alumno.id), usuario_id=actor.id,
        antes=antes, despues=_resumen_alumno(alumno), ip=ip,
    )
    return alumno


def vincular_acudiente(
    db: Session, alumno: Alumno, *, acudiente_id: uuid.UUID, parentesco: str, principal: bool,
    actor: Usuario, ip: str | None,
) -> Alumno:
    _vincular(db, alumno, acudiente_id=acudiente_id, parentesco=parentesco, principal=principal)
    db.flush()
    auditoria.registrar(
        db, accion="alumno.vincular_acudiente", entidad="alumno", entidad_id=str(alumno.id), usuario_id=actor.id,
        despues={"acudiente_id": str(acudiente_id), "parentesco": parentesco, "principal": principal}, ip=ip,
    )
    return alumno


def desvincular_acudiente(
    db: Session, alumno: Alumno, *, acudiente_id: uuid.UUID, actor: Usuario, ip: str | None
) -> Alumno:
    vinculo = next((v for v in alumno.vinculos if v.acudiente_id == acudiente_id), None)
    if vinculo is None:
        raise NoEncontrado("Ese acudiente no está vinculado al alumno.")
    if len(alumno.vinculos) == 1 and es_menor(db, alumno.fecha_nacimiento):
        raise ErrorNegocio("No se puede quitar el último acudiente de un menor de edad.")
    alumno.vinculos.remove(vinculo)
    if vinculo.principal and alumno.vinculos:
        alumno.vinculos[0].principal = True
    db.flush()
    auditoria.registrar(
        db, accion="alumno.desvincular_acudiente", entidad="alumno", entidad_id=str(alumno.id),
        usuario_id=actor.id, antes={"acudiente_id": str(acudiente_id), "parentesco": vinculo.parentesco}, ip=ip,
    )
    return alumno


def ver_documento(db: Session, alumno: Alumno, *, actor: Usuario, ip: str | None) -> str:
    """Descifra el documento completo. Cada consulta queda en la auditoría."""
    auditoria.registrar(
        db, accion="alumno.ver_documento", entidad="alumno", entidad_id=str(alumno.id), usuario_id=actor.id, ip=ip,
    )
    return cifrado.descifrar(alumno.documento_cifrado)


# ---------- Acudientes ----------
def filtro_acudientes_visibles(usuario: Usuario) -> ColumnElement[bool]:
    """Admin/SA ven todos. El Entrenador ve los vinculados a alumnos de su rama y los aún sin vincular."""
    if "alumnos.ver_todos" in usuario.permisos_codigos:
        return true()
    de_sus_alumnos = select(AlumnoAcudiente.acudiente_id).join(Alumno).where(filtro_visibles(usuario))
    con_vinculo = select(AlumnoAcudiente.acudiente_id)
    return or_(Acudiente.id.in_(de_sus_alumnos), Acudiente.id.not_in(con_vinculo))


def obtener_acudiente(db: Session, usuario: Usuario, acudiente_id: uuid.UUID) -> Acudiente:
    acudiente = db.scalar(
        select(Acudiente).where(Acudiente.id == acudiente_id, filtro_acudientes_visibles(usuario))
    )
    if acudiente is None:
        raise NoEncontrado("Acudiente no encontrado.")
    return acudiente


def listar_acudientes(
    db: Session, usuario: Usuario, *, tipo_documento: str | None, documento: str | None, buscar: str | None,
    skip: int, limit: int,
) -> list[Acudiente]:
    if documento:
        if not tipo_documento:
            raise ErrorNegocio("Para buscar por documento indica también el tipo de documento.")
        # Búsqueda exacta por documento: permite encontrar al acudiente de un hermano en la otra rama para
        # vincularlo (sin duplicarlo). Exige conocer el número completo, así que no sirve para curiosear.
        q = select(Acudiente).where(
            Acudiente.documento_indice == cifrado.indice_ciego(f"{tipo_documento}:{documento}")
        )
    else:
        q = select(Acudiente).where(filtro_acudientes_visibles(usuario))
    if buscar:
        q = q.where(or_(
            Acudiente.nombres.icontains(buscar, autoescape=True),
            Acudiente.apellidos.icontains(buscar, autoescape=True),
        ))
    return list(db.scalars(q.order_by(Acudiente.apellidos, Acudiente.nombres).offset(skip).limit(limit)))


def crear_acudiente(db: Session, *, datos: dict[str, Any], actor: Usuario, ip: str | None) -> Acudiente:
    _aplicar_documento(datos)
    _verificar_documento_libre(db, Acudiente, datos)
    _verificar_usuario(db, Acudiente, datos)
    acudiente = Acudiente(**datos)
    db.add(acudiente)
    db.flush()
    auditoria.registrar(
        db, accion="acudiente.crear", entidad="acudiente", entidad_id=str(acudiente.id), usuario_id=actor.id,
        despues=_resumen_acudiente(acudiente), ip=ip,
    )
    return acudiente


def actualizar_acudiente(
    db: Session, acudiente: Acudiente, *, cambios: dict[str, Any], actor: Usuario, ip: str | None
) -> Acudiente:
    antes = _resumen_acudiente(acudiente)
    _aplicar_documento(cambios, acudiente)
    _verificar_documento_libre(db, Acudiente, cambios, acudiente.id)
    _verificar_usuario(db, Acudiente, cambios, acudiente.id)
    for campo, valor in cambios.items():
        setattr(acudiente, campo, valor)
    db.flush()
    auditoria.registrar(
        db, accion="acudiente.actualizar", entidad="acudiente", entidad_id=str(acudiente.id), usuario_id=actor.id,
        antes=antes, despues=_resumen_acudiente(acudiente), ip=ip,
    )
    return acudiente
