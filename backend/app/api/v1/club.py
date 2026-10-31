"""Panel del perfil del club (lo que se publica en el sitio). Todo exige `club.editar`."""
import uuid

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import ip_cliente, requiere
from app.core.almacen import Almacen, get_almacen
from app.core.config import get_settings
from app.db.session import get_db
from app.models.acceso import Usuario
from app.models.club import Album, IntegranteEquipo, Video
from app.schemas.club import (
    AlbumCambios,
    AlbumIn,
    AlbumOut,
    ClubPanelOut,
    FotoOut,
    IntegranteCambios,
    IntegranteIn,
    IntegranteOut,
    PerfilIn,
    PerfilOut,
    VideoCambios,
    VideoIn,
    VideoOut,
)
from app.services import club as servicio
from app.services import configuracion
from app.services.errores import ErrorNegocio, NoEncontrado

router = APIRouter(prefix="/club", tags=["club"])
EDITAR = requiere("club.editar")


@router.get("", response_model=ClubPanelOut)
def ver(_: Usuario = Depends(EDITAR), db: Session = Depends(get_db)) -> ClubPanelOut:
    url = get_settings().sitio_url.strip()
    return ClubPanelOut(
        sitio_url=url if url.startswith(("https://", "http://localhost")) else None,
        perfil=PerfilOut.model_validate(servicio.perfil(db)),
        albumes=[AlbumOut.model_validate(a) for a in
                 db.scalars(select(Album).order_by(Album.fecha.desc().nulls_last(), Album.creado_en.desc()))],
        videos=[VideoOut.model_validate(v) for v in db.scalars(select(Video).order_by(Video.creado_en.desc()))],
        equipo=[IntegranteOut.model_validate(i) for i in
                db.scalars(select(IntegranteEquipo).order_by(IntegranteEquipo.orden, IntegranteEquipo.nombre))],
    )


@router.patch("/perfil", response_model=PerfilOut)
def actualizar_perfil(
    datos: PerfilIn, request: Request, actor: Usuario = Depends(EDITAR), db: Session = Depends(get_db)
) -> PerfilOut:
    cambios = datos.model_dump(exclude_unset=True)
    if "nombre" in cambios and not cambios["nombre"]:
        raise ErrorNegocio("El nombre del club es obligatorio.")
    if cambios.get("publicado") is None:
        cambios.pop("publicado", None)
    p = servicio.actualizar_perfil(db, cambios, actor=actor, ip=ip_cliente(request))
    db.commit()
    return PerfilOut.model_validate(p)


# ---------- Álbumes y fotos ----------
@router.post("/albumes", response_model=AlbumOut, status_code=status.HTTP_201_CREATED)
def crear_album(
    datos: AlbumIn, request: Request, actor: Usuario = Depends(EDITAR), db: Session = Depends(get_db)
) -> AlbumOut:
    a = Album(**datos.model_dump())
    db.add(a)
    db.flush()
    servicio.auditar(db, "club.album_crear", "album", a.id, actor, ip_cliente(request), despues={"nombre": a.nombre})
    db.commit()
    db.refresh(a)
    return AlbumOut.model_validate(a)


@router.patch("/albumes/{album_id}", response_model=AlbumOut)
def actualizar_album(
    album_id: uuid.UUID, datos: AlbumCambios, request: Request, actor: Usuario = Depends(EDITAR),
    db: Session = Depends(get_db),
) -> AlbumOut:
    a = servicio.obtener_album(db, album_id)
    cambios = {k: v for k, v in datos.model_dump(exclude_unset=True).items() if v is not None or k == "fecha"}
    for k, v in cambios.items():
        setattr(a, k, v)
    servicio.auditar(db, "club.album_editar", "album", a.id, actor, ip_cliente(request),
                      despues={k: str(v) for k, v in cambios.items()})
    db.commit()
    return AlbumOut.model_validate(a)


@router.delete("/albumes/{album_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_album(
    album_id: uuid.UUID, request: Request, actor: Usuario = Depends(EDITAR), db: Session = Depends(get_db),
    almacen: Almacen = Depends(get_almacen),
) -> Response:
    a = servicio.obtener_album(db, album_id)
    claves = servicio.claves_de(a.fotos)
    servicio.auditar(db, "club.album_eliminar", "album", a.id, actor, ip_cliente(request),
                      antes={"nombre": a.nombre, "fotos": len(a.fotos)})
    db.delete(a)
    db.commit()
    for c in claves:  # después del commit: si la transacción falla, los archivos siguen ahí
        almacen.borrar(c)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/albumes/{album_id}/fotos", response_model=FotoOut, status_code=status.HTTP_201_CREATED)
def subir_foto(
    album_id: uuid.UUID,
    request: Request,
    archivo: UploadFile = File(),
    autorizacion: bool = Form(),
    actor: Usuario = Depends(EDITAR),
    db: Session = Depends(get_db),
    almacen: Almacen = Depends(get_almacen),
) -> FotoOut:
    if not autorizacion:
        raise ErrorNegocio("Confirma que tienes autorización de los acudientes de los menores que aparecen.")
    a = servicio.obtener_album(db, album_id)
    maximo = configuracion.obtener(db, "foto_max_mb") * 1024 * 1024
    datos = archivo.file.read(maximo + 1)  # nunca se lee más de lo permitido
    foto = servicio.subir_foto(db, a, datos, almacen=almacen, actor=actor, ip=ip_cliente(request))
    db.commit()
    return FotoOut.model_validate(foto)


@router.get("/fotos/{foto_id}")
def ver_foto(
    foto_id: uuid.UUID, tam: str = Query("mini", pattern="^(mini|grande)$"), _: Usuario = Depends(EDITAR),
    db: Session = Depends(get_db), almacen: Almacen = Depends(get_almacen),
) -> Response:
    """Vista previa en el panel (incluye álbumes sin publicar)."""
    foto = servicio.obtener_foto(db, foto_id, solo_publicada=False)
    datos = almacen.leer(foto.clave_miniatura if tam == "mini" else foto.clave)
    return Response(datos, media_type="image/jpeg", headers={"Cache-Control": "private, no-store"})


@router.delete("/fotos/{foto_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_foto(
    foto_id: uuid.UUID, request: Request, actor: Usuario = Depends(EDITAR), db: Session = Depends(get_db),
    almacen: Almacen = Depends(get_almacen),
) -> Response:
    foto = servicio.obtener_foto(db, foto_id, solo_publicada=False)
    claves = servicio.claves_de([foto])
    servicio.auditar(db, "club.foto_eliminar", "foto", foto.id, actor, ip_cliente(request))
    db.delete(foto)
    db.commit()
    for c in claves:
        almacen.borrar(c)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Videos ----------
def _video(db: Session, video_id: uuid.UUID) -> Video:
    v = db.get(Video, video_id)
    if v is None:
        raise NoEncontrado("Video no encontrado.")
    return v


@router.post("/videos", response_model=VideoOut, status_code=status.HTTP_201_CREATED)
def crear_video(
    datos: VideoIn, request: Request, actor: Usuario = Depends(EDITAR), db: Session = Depends(get_db)
) -> VideoOut:
    v = Video(titulo=datos.titulo, youtube_id=servicio.youtube_id(datos.enlace), publicado=datos.publicado)
    db.add(v)
    db.flush()
    servicio.auditar(db, "club.video_crear", "video", v.id, actor, ip_cliente(request), despues={"titulo": v.titulo})
    db.commit()
    return VideoOut.model_validate(v)


@router.patch("/videos/{video_id}", response_model=VideoOut)
def actualizar_video(
    video_id: uuid.UUID, datos: VideoCambios, request: Request, actor: Usuario = Depends(EDITAR),
    db: Session = Depends(get_db),
) -> VideoOut:
    v = _video(db, video_id)
    cambios = {k: val for k, val in datos.model_dump(exclude_unset=True).items() if val is not None}
    for k, val in cambios.items():
        setattr(v, k, val)
    servicio.auditar(db, "club.video_editar", "video", v.id, actor, ip_cliente(request), despues=cambios)
    db.commit()
    return VideoOut.model_validate(v)


@router.delete("/videos/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_video(
    video_id: uuid.UUID, request: Request, actor: Usuario = Depends(EDITAR), db: Session = Depends(get_db)
) -> Response:
    v = _video(db, video_id)
    servicio.auditar(db, "club.video_eliminar", "video", v.id, actor, ip_cliente(request),
                      antes={"titulo": v.titulo})
    db.delete(v)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Equipo de trabajo ----------
def _integrante(db: Session, integrante_id: uuid.UUID) -> IntegranteEquipo:
    i = db.get(IntegranteEquipo, integrante_id)
    if i is None:
        raise NoEncontrado("Integrante no encontrado.")
    return i


@router.post("/equipo", response_model=IntegranteOut, status_code=status.HTTP_201_CREATED)
def crear_integrante(
    datos: IntegranteIn, request: Request, actor: Usuario = Depends(EDITAR), db: Session = Depends(get_db)
) -> IntegranteOut:
    i = IntegranteEquipo(**datos.model_dump())
    db.add(i)
    db.flush()
    servicio.auditar(db, "club.equipo_crear", "integrante", i.id, actor, ip_cliente(request),
                      despues={"nombre": i.nombre, "cargo": i.cargo})
    db.commit()
    return IntegranteOut.model_validate(i)


@router.patch("/equipo/{integrante_id}", response_model=IntegranteOut)
def actualizar_integrante(
    integrante_id: uuid.UUID, datos: IntegranteCambios, request: Request, actor: Usuario = Depends(EDITAR),
    db: Session = Depends(get_db),
) -> IntegranteOut:
    i = _integrante(db, integrante_id)
    cambios = {k: v for k, v in datos.model_dump(exclude_unset=True).items() if v is not None or k == "bio"}
    for k, v in cambios.items():
        setattr(i, k, v or None if k == "bio" else v)
    servicio.auditar(db, "club.equipo_editar", "integrante", i.id, actor, ip_cliente(request), despues=cambios)
    db.commit()
    return IntegranteOut.model_validate(i)


@router.delete("/equipo/{integrante_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_integrante(
    integrante_id: uuid.UUID, request: Request, actor: Usuario = Depends(EDITAR), db: Session = Depends(get_db)
) -> Response:
    i = _integrante(db, integrante_id)
    servicio.auditar(db, "club.equipo_eliminar", "integrante", i.id, actor, ip_cliente(request),
                      antes={"nombre": i.nombre})
    db.delete(i)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
