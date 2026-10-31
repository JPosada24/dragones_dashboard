"""Operaciones del panel sobre el contenido del sitio: álbumes, fotos, portadas, videos y equipo técnico.

Las funciones que dejan archivos sin uso devuelven sus claves: la ruta los borra del almacén **después** del commit,
así un fallo de la transacción nunca deja filas apuntando a archivos inexistentes.
"""
import uuid
from typing import Any, BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.acceso import Usuario
from app.models.club import Album, Foto, IntegranteEquipo, Video
from app.services import configuracion
from app.services.club import auditar, claves_de, procesar_portada, procesar_retrato, youtube_id
from app.services.errores import ErrorNegocio, NoEncontrado

AUTORIZACION_FOTOS = "Confirma que tienes autorización de los acudientes de los menores que aparecen."


def leer_foto(db: Session, archivo: BinaryIO) -> bytes:
    """Lee la foto subida sin pasar nunca del máximo configurado (lee uno de más para saber si se pasó)."""
    mb = configuracion.obtener(db, "foto_max_mb")
    datos = archivo.read(mb * 1024 * 1024 + 1)
    if len(datos) > mb * 1024 * 1024:
        raise ErrorNegocio(f"La foto supera el máximo de {mb} MB.")
    return datos


def exigir_autorizacion(autorizacion: bool) -> None:
    if not autorizacion:
        raise ErrorNegocio(AUTORIZACION_FOTOS)


# ---------- Álbumes ----------
def listar_albumes(db: Session) -> list[Album]:
    return list(db.scalars(select(Album).order_by(Album.fecha.desc().nulls_last(), Album.creado_en.desc())))


def crear_album(db: Session, datos: dict[str, Any], *, actor: Usuario, ip: str | None) -> Album:
    a = Album(**datos)
    db.add(a)
    db.flush()
    auditar(db, "club.album_crear", "album", a.id, actor, ip, despues={"nombre": a.nombre})
    return a


def editar_album(db: Session, a: Album, cambios: dict[str, Any], *, actor: Usuario, ip: str | None) -> Album:
    cambios = {k: v for k, v in cambios.items() if v is not None or k == "fecha"}  # la fecha sí se puede quitar
    for k, v in cambios.items():
        setattr(a, k, v)
    auditar(db, "club.album_editar", "album", a.id, actor, ip, despues={k: str(v) for k, v in cambios.items()})
    return a


def eliminar_album(db: Session, a: Album, *, actor: Usuario, ip: str | None) -> list[str]:
    claves = claves_de(a.fotos) + ([a.portada_clave] if a.portada_clave else [])
    auditar(db, "club.album_eliminar", "album", a.id, actor, ip, antes={"nombre": a.nombre, "fotos": len(a.fotos)})
    db.delete(a)
    return claves


def cambiar_portada(
    db: Session, a: Album, datos: bytes, *, almacen: Any, actor: Usuario, ip: str | None
) -> str | None:
    """Portada propia (no cuenta como foto del álbum). Devuelve la clave de la anterior, para borrarla."""
    nueva, anterior = uuid.uuid4().hex, a.portada_clave
    almacen.guardar(nueva, procesar_portada(datos))
    a.portada_clave = nueva
    auditar(db, "club.album_portada", "album", a.id, actor, ip)
    return anterior


def quitar_portada(db: Session, a: Album, *, actor: Usuario, ip: str | None) -> str | None:
    anterior, a.portada_clave = a.portada_clave, None
    auditar(db, "club.album_portada_quitar", "album", a.id, actor, ip)
    return anterior


# ---------- Fotos ----------
def eliminar_fotos(db: Session, ids: set[uuid.UUID], *, actor: Usuario, ip: str | None) -> tuple[int, list[str]]:
    """Varias fotos de una vez (todas o ninguna). Las que ya no existen se ignoran."""
    fotos = list(db.scalars(select(Foto).where(Foto.id.in_(ids))))
    claves = claves_de(fotos)
    for f in fotos:
        db.delete(f)
    auditar(db, "club.fotos_eliminar", "foto", len(fotos), actor, ip, antes={"ids": [str(f.id) for f in fotos]})
    return len(fotos), claves


def eliminar_foto(db: Session, foto: Foto, *, actor: Usuario, ip: str | None) -> list[str]:
    claves = claves_de([foto])
    auditar(db, "club.foto_eliminar", "foto", foto.id, actor, ip)
    db.delete(foto)
    return claves


# ---------- Videos ----------
def listar_videos(db: Session) -> list[Video]:
    return list(db.scalars(select(Video).order_by(Video.creado_en.desc())))


def obtener_video(db: Session, video_id: uuid.UUID) -> Video:
    v = db.get(Video, video_id)
    if v is None:
        raise NoEncontrado("Video no encontrado.")
    return v


def crear_video(db: Session, titulo: str, enlace: str, publicado: bool, *, actor: Usuario, ip: str | None) -> Video:
    v = Video(titulo=titulo, youtube_id=youtube_id(enlace), publicado=publicado)
    db.add(v)
    db.flush()
    auditar(db, "club.video_crear", "video", v.id, actor, ip, despues={"titulo": v.titulo})
    return v


def editar_video(db: Session, v: Video, cambios: dict[str, Any], *, actor: Usuario, ip: str | None) -> Video:
    cambios = {k: val for k, val in cambios.items() if val is not None}
    for k, val in cambios.items():
        setattr(v, k, val)
    auditar(db, "club.video_editar", "video", v.id, actor, ip, despues=cambios)
    return v


def eliminar_video(db: Session, v: Video, *, actor: Usuario, ip: str | None) -> None:
    auditar(db, "club.video_eliminar", "video", v.id, actor, ip, antes={"titulo": v.titulo})
    db.delete(v)


# ---------- Equipo técnico ----------
def listar_equipo(db: Session) -> list[IntegranteEquipo]:
    return list(db.scalars(select(IntegranteEquipo).order_by(IntegranteEquipo.orden, IntegranteEquipo.nombre)))


def obtener_integrante(db: Session, integrante_id: uuid.UUID) -> IntegranteEquipo:
    i = db.get(IntegranteEquipo, integrante_id)
    if i is None:
        raise NoEncontrado("Integrante no encontrado.")
    return i


def crear_integrante(db: Session, datos: dict[str, Any], *, actor: Usuario, ip: str | None) -> IntegranteEquipo:
    i = IntegranteEquipo(**datos)
    db.add(i)
    db.flush()
    auditar(db, "club.equipo_crear", "integrante", i.id, actor, ip, despues={"nombre": i.nombre, "cargo": i.cargo})
    return i


def editar_integrante(
    db: Session, i: IntegranteEquipo, cambios: dict[str, Any], *, actor: Usuario, ip: str | None
) -> IntegranteEquipo:
    cambios = {k: v for k, v in cambios.items() if v is not None or k == "bio"}  # la presentación sí se puede quitar
    for k, v in cambios.items():
        setattr(i, k, (v or None) if k == "bio" else v)
    auditar(db, "club.equipo_editar", "integrante", i.id, actor, ip, despues=cambios)
    return i


def eliminar_integrante(db: Session, i: IntegranteEquipo, *, actor: Usuario, ip: str | None) -> str | None:
    clave = i.foto_clave
    auditar(db, "club.equipo_eliminar", "integrante", i.id, actor, ip, antes={"nombre": i.nombre})
    db.delete(i)
    return clave


def cambiar_retrato(
    db: Session, i: IntegranteEquipo, datos: bytes, *, almacen: Any, actor: Usuario, ip: str | None
) -> str | None:
    """Foto del integrante. Devuelve la clave de la anterior, para borrarla tras el commit."""
    nueva, anterior = uuid.uuid4().hex, i.foto_clave
    almacen.guardar(nueva, procesar_retrato(datos))
    i.foto_clave = nueva
    auditar(db, "club.equipo_foto", "integrante", i.id, actor, ip)
    return anterior


def quitar_retrato(db: Session, i: IntegranteEquipo, *, actor: Usuario, ip: str | None) -> str | None:
    anterior, i.foto_clave = i.foto_clave, None
    auditar(db, "club.equipo_foto_quitar", "integrante", i.id, actor, ip)
    return anterior

