"""Sitio público del club: perfil, galería, videos, equipo de trabajo e inscripción pública de clubes a torneos."""
import io
import re
import uuid
import warnings
from typing import Any
from urllib.parse import parse_qs, urlparse

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.core import fechas
from app.models.acceso import Usuario
from app.models.alumnos import Alumno, Inscripcion
from app.models.asistencia import HorarioEntrenamiento
from app.models.club import Album, Foto, IntegranteEquipo, PerfilClub, Video
from app.models.dominio import ESTADOS_VIGENTES
from app.models.torneos import EquipoTorneo, Torneo
from app.services import auditoria, configuracion, notificaciones, torneos
from app.services.errores import ErrorNegocio, NoEncontrado

# Una foto de más de 40 megapíxeles no es una foto de celular: probablemente es una "bomba" de descompresión.
Image.MAX_IMAGE_PIXELS = 40_000_000
TAMANO_GRANDE = 1920
TAMANO_MINIATURA = 480
FORMATOS = {"JPEG", "PNG", "WEBP"}
_YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_HOSTS_YOUTUBE = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be", "www.youtube-nocookie.com"}


def auditar(db: Session, accion: str, entidad: str, entidad_id: Any, actor: Usuario | None, ip: str | None,
             **extra: Any) -> None:
    auditoria.registrar(db, accion=accion, entidad=entidad, entidad_id=str(entidad_id),
                        usuario_id=actor.id if actor else None, ip=ip, **extra)


# ---------- Perfil ----------
def perfil(db: Session) -> PerfilClub:
    p = db.get(PerfilClub, 1)
    if p is None:  # la migración lo crea; esto solo protege bases a medio sembrar
        p = PerfilClub(id=1, nombre="Club Deportivo Dragones")
        db.add(p)
        db.flush()
    return p


def actualizar_perfil(
    db: Session, cambios: dict[str, Any], *, actor: Usuario, ip: str | None
) -> PerfilClub:
    p = perfil(db)
    antes = {k: getattr(p, k) for k in cambios}
    for k, v in cambios.items():
        setattr(p, k, v)
    p.actualizado_por = actor.id
    auditar(db, "club.perfil", "perfil_club", 1, actor, ip, antes=antes, despues=cambios)
    return p


# ---------- Fotos ----------
def procesar_foto(datos: bytes) -> tuple[bytes, bytes, int, int]:
    """Vuelve a codificar la imagen: corrige la orientación, quita EXIF/ubicación y genera dos tamaños.

    Re-codificar también neutraliza archivos manipulados: lo que se guarda lo produjo el servidor.
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(datos)) as original:
                if original.format not in FORMATOS:
                    raise ErrorNegocio("Solo se aceptan fotos JPG, PNG o WebP.")
                imagen = ImageOps.exif_transpose(original).convert("RGB")
    except (UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning, OSError) as e:
        raise ErrorNegocio("El archivo no es una imagen válida o es demasiado grande.") from e

    def jpeg(maximo: int) -> tuple[bytes, int, int]:
        copia = imagen.copy()
        copia.thumbnail((maximo, maximo))
        salida = io.BytesIO()
        copia.save(salida, "JPEG", quality=85, optimize=True, progressive=True)  # sin exif: no se copia
        return salida.getvalue(), copia.width, copia.height

    grande, ancho, alto = jpeg(TAMANO_GRANDE)
    miniatura, _, _ = jpeg(TAMANO_MINIATURA)
    return grande, miniatura, ancho, alto


def subir_foto(
    db: Session, album: Album, datos: bytes, *, almacen: Any, actor: Usuario, ip: str | None
) -> Foto:
    maximo = configuracion.obtener(db, "foto_max_mb") * 1024 * 1024
    if len(datos) > maximo:
        raise ErrorNegocio(f"La foto supera el máximo de {configuracion.obtener(db, 'foto_max_mb')} MB.")
    grande, miniatura, ancho, alto = procesar_foto(datos)
    clave, clave_mini = uuid.uuid4().hex, uuid.uuid4().hex
    almacen.guardar(clave, grande)
    almacen.guardar(clave_mini, miniatura)
    foto = Foto(album_id=album.id, clave=clave, clave_miniatura=clave_mini, ancho=ancho, alto=alto,
                autorizada_por=actor.id)
    db.add(foto)
    db.flush()
    auditar(db, "club.foto_subir", "foto", foto.id, actor, ip, despues={"album_id": str(album.id)})
    return foto


def claves_de(fotos: list[Foto]) -> list[str]:
    return [c for f in fotos for c in (f.clave, f.clave_miniatura)]


def obtener_album(db: Session, album_id: uuid.UUID) -> Album:
    a = db.get(Album, album_id)
    if a is None:
        raise NoEncontrado("Álbum no encontrado.")
    return a


def obtener_foto(db: Session, foto_id: uuid.UUID, *, solo_publicada: bool) -> Foto:
    q = select(Foto).join(Album, Album.id == Foto.album_id).where(Foto.id == foto_id)
    if solo_publicada:
        q = q.join(PerfilClub, PerfilClub.id == 1).where(Album.publicado.is_(True), PerfilClub.publicado.is_(True))
    foto = db.scalar(q)
    if foto is None:
        raise NoEncontrado("Foto no encontrada.")
    return foto


# ---------- Videos ----------
def youtube_id(enlace: str) -> str:
    """Saca el id de un enlace de YouTube (watch, youtu.be, shorts, embed). Cualquier otro sitio se rechaza."""
    try:
        u = urlparse(enlace.strip())
    except ValueError as e:
        raise ErrorNegocio("El enlace no es válido.") from e
    if u.scheme not in ("http", "https") or (u.hostname or "").lower() not in _HOSTS_YOUTUBE:
        raise ErrorNegocio("Solo se aceptan enlaces de YouTube.")
    if u.hostname == "youtu.be":
        candidato = u.path.lstrip("/").split("/")[0]
    elif u.path == "/watch":
        candidato = (parse_qs(u.query).get("v") or [""])[0]
    else:
        partes = [p for p in u.path.split("/") if p]
        candidato = partes[1] if len(partes) >= 2 and partes[0] in ("shorts", "embed", "live") else ""
    if not _YOUTUBE_ID.match(candidato):
        raise ErrorNegocio("No se encontró el video en ese enlace de YouTube.")
    return candidato


# ---------- Vista pública ----------
def torneos_abiertos(db: Session) -> list[tuple[Torneo, int]]:
    """Torneos con inscripciones abiertas y cuántos cupos les quedan."""
    filas = db.scalars(
        select(Torneo).where(Torneo.estado == "programado", Torneo.fecha_limite_inscripcion >= fechas.hoy())
        .order_by(Torneo.fecha_inicio)
    ).all()
    return [(t, max(0, t.cupo_equipos - torneos.resumen(db, t)["ocupados"])) for t in filas]


def cifras(db: Session, p: PerfilClub) -> dict[str, Any]:
    """Totales para la portada del sitio. Solo números agregados: nada identifica a un alumno."""
    hoy = fechas.hoy()
    por_rama = dict(db.execute(
        select(Alumno.rama, func.count(func.distinct(Alumno.id)))
        .join(Inscripcion, Inscripcion.alumno_id == Alumno.id)
        .where(Alumno.activo.is_(True), Inscripcion.anio == hoy.year, Inscripcion.estado.in_(ESTADOS_VIGENTES))
        .group_by(Alumno.rama)
    ).all())
    return {
        "deportistas_activos": sum(por_rama.values()),
        "femenina": por_rama.get("femenina", 0),
        "masculina": por_rama.get("masculina", 0),
        "entrenamientos_semana": db.scalar(select(func.count()).select_from(HorarioEntrenamiento)) or 0,
        "torneos_anio": db.scalar(select(func.count()).select_from(Torneo).where(
            extract("year", Torneo.fecha_inicio) == hoy.year, Torneo.estado == "programado")) or 0,
        "anios": hoy.year - p.fundado_en if p.fundado_en and p.fundado_en <= hoy.year else None,
    }


def publico(db: Session) -> dict[str, Any]:
    p = perfil(db)
    if not p.publicado:
        raise NoEncontrado("El sitio del club aún no está publicado.")
    albumes = db.scalars(
        select(Album).where(Album.publicado.is_(True)).order_by(Album.fecha.desc().nulls_last(), Album.creado_en.desc())
    ).all()
    return {
        "perfil": p,
        "cifras": cifras(db, p),
        "horario": db.scalars(select(HorarioEntrenamiento).order_by(
            HorarioEntrenamiento.dia_semana, HorarioEntrenamiento.hora_inicio)).all(),
        "albumes": [a for a in albumes if a.fotos],
        "videos": db.scalars(select(Video).where(Video.publicado.is_(True)).order_by(Video.creado_en.desc())).all(),
        "equipo": db.scalars(select(IntegranteEquipo).where(IntegranteEquipo.publicado.is_(True))
                             .order_by(IntegranteEquipo.orden, IntegranteEquipo.nombre)).all(),
        "torneos": torneos_abiertos(db),
    }


def obtener_torneo_abierto(db: Session, torneo_id: uuid.UUID) -> Torneo:
    if not perfil(db).publicado:
        raise NoEncontrado("El sitio del club aún no está publicado.")
    t = db.get(Torneo, torneo_id)
    if t is None or t.estado == "eliminado":
        raise NoEncontrado("Torneo no encontrado.")
    return t


def inscribir_desde_sitio(
    db: Session, torneo: Torneo, datos: dict[str, Any], *, ip: str | None
) -> EquipoTorneo:
    """Un club externo se inscribe solo. Mismas reglas de cupo y plazo que desde el panel; se avisa al staff."""
    equipo = torneos.inscribir(db, torneo, datos=datos, actor=None, ip=ip)
    equipo.origen = "sitio"
    equipo.autoriza_datos_en = fechas.ahora()
    estado = {"en_espera": "en lista de espera", "confirmado": "confirmado"}.get(equipo.estado, "pendiente de pago")
    notificaciones.avisar(
        db, notificaciones.staff_de_rama(db, torneo.rama), tipo="torneo_inscripcion_sitio",
        clave=f"torneo-sitio-{equipo.id}", titulo=f"Nuevo club inscrito: {equipo.nombre_club}",
        mensaje=(f"{equipo.nombre_club} ({equipo.ciudad}) se inscribió desde el sitio a «{torneo.nombre}». "
                 f"Quedó {estado}. Delegado: {equipo.delegado_nombre}."),
    )
    return equipo
