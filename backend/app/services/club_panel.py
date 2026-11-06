"""Operaciones del panel sobre el contenido del sitio: álbumes, fotos, portadas, videos, equipo y torneos realizados.

Las funciones que dejan archivos sin uso devuelven sus claves: la ruta los borra del almacén **después** del commit,
así un fallo de la transacción nunca deja filas apuntando a archivos inexistentes.
"""
import uuid
from typing import Any, BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import fechas
from app.models.acceso import Usuario
from app.models.club import Album, Foto, IntegranteEquipo, TorneoRealizado, Video
from app.models.torneos import Torneo
from app.services import configuracion
from app.services.club import (
    MINIATURA_ANUNCIO,
    auditar,
    claves_de,
    procesar_foto,
    procesar_portada,
    procesar_retrato,
    youtube_id,
)
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


# ---------- Torneos realizados ----------
def listar_torneos_realizados(db: Session) -> list[TorneoRealizado]:
    return list(db.scalars(select(TorneoRealizado).order_by(TorneoRealizado.fecha.desc(), TorneoRealizado.nombre)))


def obtener_torneo_realizado(db: Session, torneo_id: uuid.UUID) -> TorneoRealizado:
    t = db.get(TorneoRealizado, torneo_id)
    if t is None:
        raise NoEncontrado("Torneo realizado no encontrado.")
    return t


def _validar_album(db: Session, album_id: uuid.UUID | None) -> None:
    if album_id is not None and db.get(Album, album_id) is None:
        raise ErrorNegocio("El álbum elegido ya no existe.")


def crear_torneo_realizado(db: Session, datos: dict[str, Any], *, actor: Usuario, ip: str | None) -> TorneoRealizado:
    _validar_album(db, datos.get("album_id"))
    t = TorneoRealizado(**datos)
    db.add(t)
    db.flush()
    auditar(db, "club.torneo_realizado_crear", "torneo_realizado", t.id, actor, ip,
            despues={"nombre": t.nombre, "fecha": str(t.fecha)})
    return t


def editar_torneo_realizado(
    db: Session, t: TorneoRealizado, cambios: dict[str, Any], *, actor: Usuario, ip: str | None
) -> TorneoRealizado:
    # lugar, resumen y álbum se pueden quitar (null); nombre, fecha y publicado en null = no cambiarlos.
    cambios = {k: v for k, v in cambios.items() if v is not None or k in ("lugar", "resumen", "album_id")}
    _validar_album(db, cambios.get("album_id"))
    for k, v in cambios.items():
        setattr(t, k, v)
    auditar(db, "club.torneo_realizado_editar", "torneo_realizado", t.id, actor, ip,
            despues={k: str(v) if v is not None else None for k, v in cambios.items()})
    return t


# El anuncio vive igual en un torneo abierto (flyer) y en uno realizado: mismas columnas anuncio_*.
Anunciable = Torneo | TorneoRealizado


def _claves_anuncio(t: Anunciable) -> list[str]:
    return [c for c in (t.anuncio_clave, t.anuncio_mini_clave) if c]


def _auditar_anuncio(db: Session, t: Anunciable, accion: str, actor: Usuario, ip: str | None) -> None:
    if isinstance(t, Torneo):
        auditar(db, f"torneo.{accion}", "torneo", t.id, actor, ip)
    else:
        auditar(db, f"club.torneo_realizado_{accion}", "torneo_realizado", t.id, actor, ip)


def eliminar_torneo_realizado(db: Session, t: TorneoRealizado, *, actor: Usuario, ip: str | None) -> list[str]:
    claves = _claves_anuncio(t)
    auditar(db, "club.torneo_realizado_eliminar", "torneo_realizado", t.id, actor, ip, antes={"nombre": t.nombre})
    db.delete(t)
    return claves


def cambiar_anuncio(
    db: Session, t: Anunciable, datos: bytes, *, almacen: Any, actor: Usuario, ip: str | None
) -> list[str]:
    """Anuncio (afiche) entero, sin recortar, en dos tamaños. Devuelve las claves del anterior, para borrarlas."""
    grande, mini, ancho, alto = procesar_foto(datos, miniatura=MINIATURA_ANUNCIO)
    anteriores = _claves_anuncio(t)
    t.anuncio_clave, t.anuncio_mini_clave = uuid.uuid4().hex, uuid.uuid4().hex
    almacen.guardar(t.anuncio_clave, grande)
    almacen.guardar(t.anuncio_mini_clave, mini)
    t.anuncio_ancho, t.anuncio_alto = ancho, alto
    _auditar_anuncio(db, t, "anuncio", actor, ip)
    return anteriores


def quitar_anuncio(db: Session, t: Anunciable, *, actor: Usuario, ip: str | None) -> list[str]:
    anteriores = _claves_anuncio(t)
    t.anuncio_clave = t.anuncio_mini_clave = t.anuncio_ancho = t.anuncio_alto = None
    _auditar_anuncio(db, t, "anuncio_quitar", actor, ip)
    return anteriores


def realizado_de(db: Session, torneo: Torneo) -> TorneoRealizado | None:
    return db.scalar(select(TorneoRealizado).where(TorneoRealizado.torneo_id == torneo.id))


def pasar_a_realizado(
    db: Session, torneo: Torneo, *, almacen: Any, actor: Usuario, ip: str | None
) -> TorneoRealizado:
    """Copia nombre, fecha, lugar y anuncio del torneo a «Torneos realizados», oculto hasta que le pongan resultados.

    El anuncio se copia a archivos nuevos: borrar uno de los dos nunca deja al otro sin imagen.
    """
    if torneo.estado != "programado":
        raise ErrorNegocio("Un torneo cancelado no se pasa a torneos realizados.")
    if torneo.fecha_inicio > fechas.hoy():
        raise ErrorNegocio("El torneo aún no se ha jugado: pásalo cuando empiece.")
    if realizado_de(db, torneo) is not None:
        raise ErrorNegocio("Este torneo ya está en Torneos realizados.")
    t = TorneoRealizado(nombre=torneo.nombre, fecha=torneo.fecha_inicio, lugar=torneo.lugar, publicado=False,
                        torneo_id=torneo.id)
    if torneo.anuncio_clave and torneo.anuncio_mini_clave:
        t.anuncio_clave, t.anuncio_mini_clave = uuid.uuid4().hex, uuid.uuid4().hex
        almacen.guardar(t.anuncio_clave, almacen.leer(torneo.anuncio_clave))
        almacen.guardar(t.anuncio_mini_clave, almacen.leer(torneo.anuncio_mini_clave))
        t.anuncio_ancho, t.anuncio_alto = torneo.anuncio_ancho, torneo.anuncio_alto
    db.add(t)
    db.flush()
    auditar(db, "club.torneo_realizado_crear", "torneo_realizado", t.id, actor, ip,
            despues={"nombre": t.nombre, "fecha": str(t.fecha), "torneo_id": str(torneo.id)})
    return t
