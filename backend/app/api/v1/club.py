"""Panel del perfil del club (lo que se publica en el sitio). Todo exige `club.editar`.

Las rutas solo traducen HTTP: la lógica vive en `services/club.py` y `services/club_panel.py`.
"""
import uuid
from collections.abc import Iterable

from fastapi import APIRouter, Depends, File, Form, Query, Request, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import ip_cliente, requiere
from app.core.almacen import Almacen, get_almacen
from app.core.config import get_settings
from app.db.session import get_db
from app.models.acceso import Usuario
from app.schemas.club import (
    AlbumCambios,
    AlbumIn,
    AlbumOut,
    ClubPanelOut,
    EliminarFotosIn,
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
from app.services import club_panel as panel
from app.services.errores import NoEncontrado

router = APIRouter(prefix="/club", tags=["club"])
EDITAR = requiere("club.editar")
SIN_CACHE = {"Cache-Control": "private, no-store"}


def _confirmar(db: Session, almacen: Almacen, claves: Iterable[str | None]) -> None:
    """Confirma la transacción y solo entonces borra los archivos que quedaron sin uso."""
    db.commit()
    for clave in claves:
        if clave:
            almacen.borrar(clave)


def _jpeg(datos: bytes) -> Response:
    return Response(datos, media_type="image/jpeg", headers=SIN_CACHE)


@router.get("", response_model=ClubPanelOut)
def ver(_: Usuario = Depends(EDITAR), db: Session = Depends(get_db)) -> ClubPanelOut:
    url = get_settings().sitio_url.strip()
    return ClubPanelOut(
        sitio_url=url if url.startswith(("https://", "http://localhost")) else None,
        perfil=PerfilOut.model_validate(servicio.perfil(db)),
        albumes=[AlbumOut.model_validate(a) for a in panel.listar_albumes(db)],
        videos=[VideoOut.model_validate(v) for v in panel.listar_videos(db)],
        equipo=[IntegranteOut.model_validate(i) for i in panel.listar_equipo(db)],
    )


@router.patch("/perfil", response_model=PerfilOut)
def actualizar_perfil(
    datos: PerfilIn, request: Request, actor: Usuario = Depends(EDITAR), db: Session = Depends(get_db)
) -> PerfilOut:
    p = servicio.actualizar_perfil(db, datos.model_dump(exclude_unset=True), actor=actor, ip=ip_cliente(request))
    db.commit()
    return PerfilOut.model_validate(p)


# ---------- Álbumes y fotos ----------
@router.get("/albumes", response_model=list[AlbumOut])
def listar_albumes(_: Usuario = Depends(EDITAR), db: Session = Depends(get_db)) -> list[AlbumOut]:
    return [AlbumOut.model_validate(a) for a in panel.listar_albumes(db)]


@router.post("/albumes", response_model=AlbumOut, status_code=status.HTTP_201_CREATED)
def crear_album(
    datos: AlbumIn, request: Request, actor: Usuario = Depends(EDITAR), db: Session = Depends(get_db)
) -> AlbumOut:
    a = panel.crear_album(db, datos.model_dump(), actor=actor, ip=ip_cliente(request))
    db.commit()
    db.refresh(a)
    return AlbumOut.model_validate(a)


@router.patch("/albumes/{album_id}", response_model=AlbumOut)
def actualizar_album(
    album_id: uuid.UUID, datos: AlbumCambios, request: Request, actor: Usuario = Depends(EDITAR),
    db: Session = Depends(get_db),
) -> AlbumOut:
    a = panel.editar_album(
        db, servicio.obtener_album(db, album_id), datos.model_dump(exclude_unset=True),
        actor=actor, ip=ip_cliente(request),
    )
    db.commit()
    return AlbumOut.model_validate(a)


@router.delete("/albumes/{album_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_album(
    album_id: uuid.UUID, request: Request, actor: Usuario = Depends(EDITAR), db: Session = Depends(get_db),
    almacen: Almacen = Depends(get_almacen),
) -> Response:
    claves = panel.eliminar_album(db, servicio.obtener_album(db, album_id), actor=actor, ip=ip_cliente(request))
    _confirmar(db, almacen, claves)
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
    panel.exigir_autorizacion(autorizacion)
    a = servicio.obtener_album(db, album_id)
    foto = servicio.subir_foto(
        db, a, panel.leer_foto(db, archivo.file), almacen=almacen, actor=actor, ip=ip_cliente(request),
    )
    db.commit()
    return FotoOut.model_validate(foto)


@router.get("/fotos/{foto_id}")
def ver_foto(
    foto_id: uuid.UUID, tam: str = Query("mini", pattern="^(mini|grande)$"), _: Usuario = Depends(EDITAR),
    db: Session = Depends(get_db), almacen: Almacen = Depends(get_almacen),
) -> Response:
    """Vista previa en el panel (incluye álbumes sin publicar)."""
    foto = servicio.obtener_foto(db, foto_id, solo_publicada=False)
    return _jpeg(almacen.leer(foto.clave_miniatura if tam == "mini" else foto.clave))


@router.post("/fotos/eliminar")
def eliminar_fotos(
    datos: EliminarFotosIn, request: Request, actor: Usuario = Depends(EDITAR), db: Session = Depends(get_db),
    almacen: Almacen = Depends(get_almacen),
) -> dict[str, int]:
    """Elimina varias fotos de una vez (todas o ninguna). Las que ya no existen se ignoran."""
    n, claves = panel.eliminar_fotos(db, set(datos.ids), actor=actor, ip=ip_cliente(request))
    _confirmar(db, almacen, claves)
    return {"eliminadas": n}


@router.delete("/fotos/{foto_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_foto(
    foto_id: uuid.UUID, request: Request, actor: Usuario = Depends(EDITAR), db: Session = Depends(get_db),
    almacen: Almacen = Depends(get_almacen),
) -> Response:
    foto = servicio.obtener_foto(db, foto_id, solo_publicada=False)
    _confirmar(db, almacen, panel.eliminar_foto(db, foto, actor=actor, ip=ip_cliente(request)))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Portada propia del álbum (no es una foto del álbum) ----------
@router.post("/albumes/{album_id}/portada", response_model=AlbumOut)
def subir_portada(
    album_id: uuid.UUID,
    request: Request,
    archivo: UploadFile = File(),
    autorizacion: bool = Form(),
    actor: Usuario = Depends(EDITAR),
    db: Session = Depends(get_db),
    almacen: Almacen = Depends(get_almacen),
) -> AlbumOut:
    panel.exigir_autorizacion(autorizacion)
    a = servicio.obtener_album(db, album_id)
    anterior = panel.cambiar_portada(
        db, a, panel.leer_foto(db, archivo.file), almacen=almacen, actor=actor, ip=ip_cliente(request),
    )
    _confirmar(db, almacen, [anterior])
    return AlbumOut.model_validate(a)


@router.delete("/albumes/{album_id}/portada", response_model=AlbumOut)
def quitar_portada(
    album_id: uuid.UUID, request: Request, actor: Usuario = Depends(EDITAR), db: Session = Depends(get_db),
    almacen: Almacen = Depends(get_almacen),
) -> AlbumOut:
    a = servicio.obtener_album(db, album_id)
    _confirmar(db, almacen, [panel.quitar_portada(db, a, actor=actor, ip=ip_cliente(request))])
    return AlbumOut.model_validate(a)


@router.get("/albumes/{album_id}/portada")
def ver_portada(
    album_id: uuid.UUID, _: Usuario = Depends(EDITAR), db: Session = Depends(get_db),
    almacen: Almacen = Depends(get_almacen),
) -> Response:
    a = servicio.obtener_album(db, album_id)
    if not a.portada_clave:
        raise NoEncontrado("El álbum no tiene portada propia.")
    return _jpeg(almacen.leer(a.portada_clave))


# ---------- Videos ----------
@router.get("/videos", response_model=list[VideoOut])
def listar_videos(_: Usuario = Depends(EDITAR), db: Session = Depends(get_db)) -> list[VideoOut]:
    return [VideoOut.model_validate(v) for v in panel.listar_videos(db)]


@router.post("/videos", response_model=VideoOut, status_code=status.HTTP_201_CREATED)
def crear_video(
    datos: VideoIn, request: Request, actor: Usuario = Depends(EDITAR), db: Session = Depends(get_db)
) -> VideoOut:
    v = panel.crear_video(db, datos.titulo, datos.enlace, datos.publicado, actor=actor, ip=ip_cliente(request))
    db.commit()
    return VideoOut.model_validate(v)


@router.patch("/videos/{video_id}", response_model=VideoOut)
def actualizar_video(
    video_id: uuid.UUID, datos: VideoCambios, request: Request, actor: Usuario = Depends(EDITAR),
    db: Session = Depends(get_db),
) -> VideoOut:
    v = panel.editar_video(
        db, panel.obtener_video(db, video_id), datos.model_dump(exclude_unset=True),
        actor=actor, ip=ip_cliente(request),
    )
    db.commit()
    return VideoOut.model_validate(v)


@router.delete("/videos/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_video(
    video_id: uuid.UUID, request: Request, actor: Usuario = Depends(EDITAR), db: Session = Depends(get_db)
) -> Response:
    panel.eliminar_video(db, panel.obtener_video(db, video_id), actor=actor, ip=ip_cliente(request))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------- Equipo técnico ----------
@router.get("/equipo", response_model=list[IntegranteOut])
def listar_equipo(_: Usuario = Depends(EDITAR), db: Session = Depends(get_db)) -> list[IntegranteOut]:
    return [IntegranteOut.model_validate(i) for i in panel.listar_equipo(db)]


@router.post("/equipo", response_model=IntegranteOut, status_code=status.HTTP_201_CREATED)
def crear_integrante(
    datos: IntegranteIn, request: Request, actor: Usuario = Depends(EDITAR), db: Session = Depends(get_db)
) -> IntegranteOut:
    i = panel.crear_integrante(db, datos.model_dump(), actor=actor, ip=ip_cliente(request))
    db.commit()
    return IntegranteOut.model_validate(i)


@router.patch("/equipo/{integrante_id}", response_model=IntegranteOut)
def actualizar_integrante(
    integrante_id: uuid.UUID, datos: IntegranteCambios, request: Request, actor: Usuario = Depends(EDITAR),
    db: Session = Depends(get_db),
) -> IntegranteOut:
    i = panel.editar_integrante(
        db, panel.obtener_integrante(db, integrante_id), datos.model_dump(exclude_unset=True),
        actor=actor, ip=ip_cliente(request),
    )
    db.commit()
    return IntegranteOut.model_validate(i)


@router.delete("/equipo/{integrante_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_integrante(
    integrante_id: uuid.UUID, request: Request, actor: Usuario = Depends(EDITAR), db: Session = Depends(get_db),
    almacen: Almacen = Depends(get_almacen),
) -> Response:
    i = panel.obtener_integrante(db, integrante_id)
    _confirmar(db, almacen, [panel.eliminar_integrante(db, i, actor=actor, ip=ip_cliente(request))])
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/equipo/{integrante_id}/foto", response_model=IntegranteOut)
def subir_foto_integrante(
    integrante_id: uuid.UUID,
    request: Request,
    archivo: UploadFile = File(),
    actor: Usuario = Depends(EDITAR),
    db: Session = Depends(get_db),
    almacen: Almacen = Depends(get_almacen),
) -> IntegranteOut:
    i = panel.obtener_integrante(db, integrante_id)
    anterior = panel.cambiar_retrato(
        db, i, panel.leer_foto(db, archivo.file), almacen=almacen, actor=actor, ip=ip_cliente(request),
    )
    _confirmar(db, almacen, [anterior])
    return IntegranteOut.model_validate(i)


@router.delete("/equipo/{integrante_id}/foto", response_model=IntegranteOut)
def quitar_foto_integrante(
    integrante_id: uuid.UUID, request: Request, actor: Usuario = Depends(EDITAR), db: Session = Depends(get_db),
    almacen: Almacen = Depends(get_almacen),
) -> IntegranteOut:
    i = panel.obtener_integrante(db, integrante_id)
    _confirmar(db, almacen, [panel.quitar_retrato(db, i, actor=actor, ip=ip_cliente(request))])
    return IntegranteOut.model_validate(i)


@router.get("/equipo/{integrante_id}/foto")
def ver_foto_integrante(
    integrante_id: uuid.UUID, _: Usuario = Depends(EDITAR), db: Session = Depends(get_db),
    almacen: Almacen = Depends(get_almacen),
) -> Response:
    i = panel.obtener_integrante(db, integrante_id)
    if not i.foto_clave:
        raise NoEncontrado("Sin foto.")
    return _jpeg(almacen.leer(i.foto_clave))
