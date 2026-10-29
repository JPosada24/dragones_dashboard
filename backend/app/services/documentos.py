"""Documentos del alumno: validación del archivo real, cifrado en reposo y auditoría de cada acceso."""
import hashlib
import re
import uuid
from typing import BinaryIO
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import cifrado
from app.core.almacen import Almacen
from app.models.acceso import Usuario
from app.models.alumnos import Alumno, DocumentoAlumno
from app.services import alumnos, auditoria, configuracion
from app.services.errores import ErrorNegocio, NoEncontrado

# Se mira el contenido (firma de los primeros bytes), no la extensión ni el tipo que declara el navegador.
FIRMAS: tuple[tuple[bytes, str], ...] = (
    (b"%PDF-", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
)


def detectar_mime(datos: bytes) -> str | None:
    return next((mime for firma, mime in FIRMAS if datos.startswith(firma)), None)


def _limpiar_nombre(nombre: str) -> str:
    nombre = re.sub(r"[\x00-\x1f\x7f/\\]", "", nombre.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]).strip()
    return nombre[:255] or "documento"


def content_disposition(nombre: str) -> str:
    ascii_ = re.sub(r"[^A-Za-z0-9._-]", "_", nombre)
    return f"attachment; filename=\"{ascii_}\"; filename*=UTF-8''{quote(nombre)}"


def puede_ver(db: Session, usuario: Usuario, alumno: Alumno) -> bool:
    """Staff con "alumnos.editar" (el Entrenador ya llega filtrado a su rama) o el Miembro dueño de la ficha."""
    permisos = usuario.permisos_codigos
    return "alumnos.editar" in permisos or (
        "alumnos.ver_propios" in permisos and alumnos.es_propio(db, usuario, alumno.id)
    )


def listar(db: Session, alumno: Alumno) -> list[DocumentoAlumno]:
    return list(db.scalars(
        select(DocumentoAlumno).where(DocumentoAlumno.alumno_id == alumno.id).order_by(DocumentoAlumno.creado_en)
    ))


def obtener(db: Session, alumno: Alumno, documento_id: uuid.UUID) -> DocumentoAlumno:
    doc = db.get(DocumentoAlumno, documento_id)
    if doc is None or doc.alumno_id != alumno.id:
        raise NoEncontrado("Documento no encontrado.")
    return doc


def subir(
    db: Session, alumno: Alumno, *, tipo: str, nombre_original: str, contenido: BinaryIO,
    actor: Usuario, ip: str | None, almacen: Almacen,
) -> DocumentoAlumno:
    max_mb = configuracion.obtener(db, "documento_max_mb")
    datos = contenido.read(max_mb * 1024 * 1024 + 1)  # nunca se lee más de lo permitido
    if not datos:
        raise ErrorNegocio("El archivo está vacío.")
    if len(datos) > max_mb * 1024 * 1024:
        raise ErrorNegocio(f"El archivo supera el máximo permitido de {max_mb} MB.")
    mime = detectar_mime(datos)
    if mime is None:
        raise ErrorNegocio("Formato no permitido: solo se aceptan archivos PDF, JPG o PNG.")

    clave = uuid.uuid4().hex
    almacen.guardar(clave, cifrado.cifrar_bytes(datos))
    doc = DocumentoAlumno(
        alumno_id=alumno.id, tipo=tipo, nombre_original=_limpiar_nombre(nombre_original), clave_almacen=clave,
        mime=mime, tamano=len(datos), sha256=hashlib.sha256(datos).hexdigest(), subido_por=actor.id,
    )
    db.add(doc)
    db.flush()
    auditoria.registrar(
        db, accion="documento.subir", entidad="documento_alumno", entidad_id=str(doc.id), usuario_id=actor.id,
        despues={"alumno_id": str(alumno.id), "tipo": tipo, "nombre": doc.nombre_original, "tamano": doc.tamano},
        ip=ip,
    )
    return doc


def descargar(db: Session, doc: DocumentoAlumno, *, actor: Usuario, ip: str | None, almacen: Almacen) -> bytes:
    auditoria.registrar(
        db, accion="documento.descargar", entidad="documento_alumno", entidad_id=str(doc.id), usuario_id=actor.id,
        ip=ip,
    )
    return cifrado.descifrar_bytes(almacen.leer(doc.clave_almacen))


def eliminar(db: Session, doc: DocumentoAlumno, *, actor: Usuario, ip: str | None) -> str:
    """Borra el registro y devuelve la clave del archivo: quien llama lo borra del almacén tras el commit."""
    auditoria.registrar(
        db, accion="documento.eliminar", entidad="documento_alumno", entidad_id=str(doc.id), usuario_id=actor.id,
        antes={"alumno_id": str(doc.alumno_id), "tipo": doc.tipo, "nombre": doc.nombre_original}, ip=ip,
    )
    db.delete(doc)
    db.flush()
    return doc.clave_almacen
