"""Cuentas de usuario: alta (con su vínculo a un alumno o acudiente), edición, permisos, eliminación y listado."""
import secrets
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.fechas import ahora
from app.core.permissions import PERMISOS, PERSONALIZABLES, ROLES_PERSONALIZABLES
from app.core.security import hash_password
from app.models.acceso import AjustePermiso, Permiso, Rol, SesionRefresh, Usuario
from app.models.alumnos import Acudiente, Alumno, AlumnoAcudiente
from app.services import alumnos, auditoria
from app.services.errores import Conflicto, ErrorNegocio, NoEncontrado


class EmailDuplicado(Conflicto):
    def __init__(self, email: str) -> None:
        super().__init__("Ya existe un usuario con ese correo")
        self.email = email


class RolNoExiste(ErrorNegocio):
    def __init__(self, codigo: str) -> None:
        super().__init__("El rol no existe")
        self.codigo = codigo


def obtener_rol(db: Session, codigo: str) -> Rol:
    rol = db.scalar(select(Rol).where(Rol.codigo == codigo))
    if rol is None:
        raise RolNoExiste(codigo)
    return rol


def obtener(db: Session, usuario_id: uuid.UUID) -> Usuario:
    """Una cuenta vigente; las eliminadas no existen para el panel."""
    usuario = db.get(Usuario, usuario_id)
    if usuario is None or usuario.eliminado_en is not None:
        raise NoEncontrado("Usuario no encontrado")
    return usuario


def listar(db: Session, *, skip: int, limit: int) -> list[Usuario]:
    return list(db.scalars(
        select(Usuario).where(Usuario.eliminado_en.is_(None)).order_by(Usuario.nombre).offset(skip).limit(limit)
    ))


def vinculos(db: Session, ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """A quién pertenece cada cuenta de Miembro (alumno mayor o acudiente). Tres consultas, sin importar cuántas."""
    resultado: dict[uuid.UUID, str] = {}
    for a in db.scalars(select(Alumno).where(Alumno.usuario_id.in_(ids))):
        resultado[a.usuario_id] = f"Alumno {a.codigo} · {a.nombres} {a.apellidos}"
    acudientes = {ac.id: ac.usuario_id for ac in db.scalars(select(Acudiente).where(Acudiente.usuario_id.in_(ids)))}
    hijos: dict[uuid.UUID, list[str]] = {acudiente_id: [] for acudiente_id in acudientes}
    if acudientes:
        filas = db.execute(
            select(AlumnoAcudiente.acudiente_id, Alumno.codigo, Alumno.nombres)
            .join(Alumno, Alumno.id == AlumnoAcudiente.alumno_id)
            .where(AlumnoAcudiente.acudiente_id.in_(acudientes)).order_by(Alumno.codigo)
        )
        for acudiente_id, codigo, nombres in filas:
            hijos[acudiente_id].append(f"{codigo} {nombres}")
    for acudiente_id, usuario_id in acudientes.items():
        resultado[usuario_id] = f"Acudiente de {', '.join(hijos[acudiente_id]) or 'sin alumnos'}"
    return resultado


def crear_usuario(
    db: Session, *, email: str, nombre: str, password: str, rol_codigo: str
) -> Usuario:
    """Crea el usuario. La contraseña ya debe haber pasado la política (el esquema la valida)."""
    if db.scalar(select(Usuario.id).where(Usuario.email == email)) is not None:
        raise EmailDuplicado(email)
    rol = obtener_rol(db, rol_codigo)
    usuario = Usuario(email=email, nombre=nombre, password_hash=hash_password(password), rol=rol)
    db.add(usuario)
    db.flush()
    return usuario


def _vincular(
    db: Session, usuario: Usuario, rol: str, alumno_id: uuid.UUID | None, acudiente_id: uuid.UUID | None
) -> str | None:
    """Une la cuenta de un Miembro con el alumno (mayor de edad) o el acudiente al que pertenece."""
    if not (alumno_id or acudiente_id):
        return None
    if rol != "MIEMBRO":
        raise ErrorNegocio("Solo las cuentas de Miembro se vinculan a un alumno o acudiente.")
    destino: Alumno | Acudiente | None
    if alumno_id:
        destino = db.get(Alumno, alumno_id)
        if destino is None:
            raise NoEncontrado("Alumno no encontrado.")
        if alumnos.es_menor(db, destino.fecha_nacimiento):
            raise ErrorNegocio("Un menor de edad no tiene cuenta propia: crea la cuenta para su acudiente.")
    else:
        destino = db.get(Acudiente, acudiente_id)
        if destino is None:
            raise NoEncontrado("Acudiente no encontrado.")
    if destino.usuario_id is not None:
        raise Conflicto("Ese alumno o acudiente ya tiene una cuenta.")
    destino.usuario_id = usuario.id
    return f"{'alumno' if isinstance(destino, Alumno) else 'acudiente'}:{destino.id}"


def crear_cuenta(db: Session, datos: dict[str, Any], *, actor: Usuario, ip: str | None) -> Usuario:
    """Alta desde el panel: la cuenta y, si es de un Miembro, su vínculo, en la misma transacción."""
    usuario = crear_usuario(
        db, email=datos["email"], nombre=datos["nombre"], password=datos["password"], rol_codigo=datos["rol"],
    )
    vinculo = _vincular(db, usuario, datos["rol"], datos.get("vincular_alumno_id"), datos.get("vincular_acudiente_id"))
    auditoria.registrar(
        db, accion="usuario.crear", entidad="usuario", entidad_id=str(usuario.id), usuario_id=actor.id,
        despues={"email": usuario.email, "rol": datos["rol"], "vinculo": vinculo}, ip=ip,
    )
    return usuario


def actualizar_usuario(
    db: Session, usuario: Usuario, cambios: dict[str, Any], *, actor: Usuario, ip: str | None
) -> Usuario:
    """Nombre, rol, estado o contraseña. Cambiar el rol o la contraseña invalida los tokens y cierra las sesiones."""
    if usuario.id == actor.id and (
        cambios.get("activo") is False or ("rol" in cambios and cambios["rol"] != usuario.rol.codigo)
    ):
        # Evita que el único SuperAdmin se quite el acceso a sí mismo.
        raise ErrorNegocio("No puedes cambiar tu propio rol ni desactivarte")
    antes = {"nombre": usuario.nombre, "rol": usuario.rol.codigo, "activo": usuario.activo}
    if cambios.get("nombre") is not None:
        usuario.nombre = cambios["nombre"]
    if cambios.get("rol") is not None:
        usuario.rol = obtener_rol(db, cambios["rol"])
    if cambios.get("activo") is not None:
        usuario.activo = cambios["activo"]
    nueva_clave = cambios.get("password")
    if nueva_clave is not None:
        usuario.password_hash = hash_password(nueva_clave)
    cambio_rol = usuario.rol.codigo != antes["rol"]
    reiniciados = cambio_rol and bool(usuario.ajustes)
    if cambio_rol:
        usuario.ajustes.clear()  # con el rol nuevo se empieza de cero: sus permisos son los del rol
    cambio_credenciales = nueva_clave is not None or cambio_rol
    if cambio_credenciales:
        usuario.credenciales_version += 1  # los tokens anteriores dejan de valer de inmediato
    if cambios.get("activo") is False or cambio_credenciales:
        revocar_sesiones(db, usuario.id)  # cierra todas sus sesiones abiertas
    auditoria.registrar(
        db, accion="usuario.actualizar", entidad="usuario", entidad_id=str(usuario.id), usuario_id=actor.id,
        antes=antes, despues={
            "nombre": usuario.nombre, "rol": usuario.rol.codigo, "activo": usuario.activo,
            "password_cambiada": nueva_clave is not None,  # nunca la contraseña
            "permisos_personales_reiniciados": reiniciados,
        },
        ip=ip,
    )
    return usuario


# ---------- Permisos ----------
ORDEN_ROLES = ("SUPERADMIN", "ADMIN", "ENTRENADOR", "MIEMBRO")


def roles_y_permisos(db: Session) -> tuple[list[Permiso], list[Rol]]:
    """Catálogo de permisos y los roles del más al menos privilegiado (matriz de Usuarios)."""
    permisos = list(db.scalars(select(Permiso).order_by(Permiso.codigo)))
    roles = sorted(
        db.scalars(select(Rol)),
        key=lambda r: ORDEN_ROLES.index(r.codigo) if r.codigo in ORDEN_ROLES else len(ORDEN_ROLES),
    )
    return permisos, roles


def permisos_de(usuario: Usuario) -> dict[str, Any]:
    """Los permisos de una persona: los de su rol, los que se le dieron, los que se le quitaron y el resultado."""
    personalizable = usuario.rol.codigo in ROLES_PERSONALIZABLES
    ajustes = usuario.ajustes if personalizable else []
    return {
        "rol": usuario.rol.codigo,
        "personalizable": personalizable,
        "de_rol": sorted(p.codigo for p in usuario.rol.permisos),
        "concedidos": sorted(a.permiso.codigo for a in ajustes if a.concedido),
        "quitados": sorted(a.permiso.codigo for a in ajustes if not a.concedido),
        "efectivos": usuario.permisos_codigos,
    }


def ajustar_permisos(
    db: Session, usuario: Usuario, permisos: set[str], *, actor: Usuario, ip: str | None
) -> Usuario:
    """Deja a la persona con exactamente `permisos` (dentro de lo que se puede dar): lo que su rol no trae se le da
    y lo que trae y no está se le quita. Aplica desde la siguiente petición; no cierra sus sesiones."""
    if usuario.id == actor.id:
        raise ErrorNegocio("No puedes cambiar tus propios permisos.")
    if usuario.rol.codigo not in ROLES_PERSONALIZABLES:
        raise ErrorNegocio(
            "Solo se ajustan permisos de Admin y Entrenador: el SuperAdmin siempre los tiene todos y una cuenta de "
            "familia solo consulta lo suyo."
        )
    desconocidos = permisos - PERMISOS.keys()
    if desconocidos:
        raise ErrorNegocio(f"Permisos que no existen: {', '.join(sorted(desconocidos))}.")
    vetados = permisos - PERSONALIZABLES
    if vetados:
        raise ErrorNegocio(f"Estos permisos no se le pueden dar a una persona: {', '.join(sorted(vetados))}.")

    de_rol = {p.codigo for p in usuario.rol.permisos}
    conceder = permisos - de_rol
    quitar = (de_rol & PERSONALIZABLES) - permisos
    antes = permisos_de(usuario)
    usuario.ajustes.clear()
    db.flush()  # borra los ajustes anteriores antes de insertar los nuevos (misma llave primaria)
    catalogo = {p.codigo: p for p in db.scalars(select(Permiso).where(Permiso.codigo.in_(conceder | quitar)))}
    for codigo in sorted(conceder):
        usuario.ajustes.append(AjustePermiso(permiso=catalogo[codigo], concedido=True))
    for codigo in sorted(quitar):
        usuario.ajustes.append(AjustePermiso(permiso=catalogo[codigo], concedido=False))
    db.flush()
    despues = permisos_de(usuario)
    auditoria.registrar(
        db, accion="usuario.permisos", entidad="usuario", entidad_id=str(usuario.id), usuario_id=actor.id,
        antes={"concedidos": antes["concedidos"], "quitados": antes["quitados"]},
        despues={"concedidos": despues["concedidos"], "quitados": despues["quitados"]}, ip=ip,
    )
    return usuario


def revocar_sesiones(db: Session, usuario_id: uuid.UUID) -> None:
    db.execute(
        update(SesionRefresh)
        .where(SesionRefresh.usuario_id == usuario_id, SesionRefresh.revocado_en.is_(None))
        .values(revocado_en=datetime.now(UTC))
    )


def eliminar_usuario(db: Session, usuario: Usuario, *, actor: Usuario, ip: str | None) -> None:
    """Elimina una cuenta: nadie vuelve a entrar con ella y su correo queda libre para otra cuenta.

    No se borra la fila: pagos, asistencias, actas y la auditoría guardan quién los registró (y la auditoría no se
    toca). Se conserva solo el nombre, para que ese historial siga diciendo quién fue; el correo se descarta.
    """
    if usuario.id == actor.id:
        raise ErrorNegocio("No puedes eliminar tu propia cuenta.")
    vinculo = None
    for modelo in (Alumno, Acudiente):
        fila = db.scalar(select(modelo).where(modelo.usuario_id == usuario.id))
        if fila is not None:
            vinculo = f"{modelo.__tablename__}:{fila.id}"
            fila.usuario_id = None  # el alumno o acudiente sigue; solo pierde la cuenta
    antes = {"rol": usuario.rol.codigo, "activo": usuario.activo, "vinculo": vinculo}
    usuario.email = f"eliminado-{usuario.id.hex}@usuarios.invalid"
    usuario.password_hash = hash_password(secrets.token_urlsafe(32))  # nadie la conoce
    usuario.activo = False
    usuario.credenciales_version += 1  # los tokens que tenga dejan de valer al instante
    usuario.eliminado_en = ahora()
    revocar_sesiones(db, usuario.id)
    db.flush()
    auditoria.registrar(
        db, accion="usuario.eliminar", entidad="usuario", entidad_id=str(usuario.id), usuario_id=actor.id,
        antes=antes, despues={"eliminado": True}, ip=ip,
    )
