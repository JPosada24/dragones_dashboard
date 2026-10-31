"""Sitio público del club: se ve sin iniciar sesión. Solo expone lo publicado y nada privado de los alumnos."""
import uuid

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import ip_cliente
from app.core.almacen import Almacen, get_almacen
from app.core.limites import limitador_sitio
from app.db.session import get_db
from app.schemas.club import (
    AlbumOut,
    HorarioPublicoOut,
    InscripcionSitioIn,
    InscripcionSitioOut,
    IntegranteOut,
    PerfilOut,
    SitioOut,
    TorneoPublicoOut,
    VideoOut,
)
from app.services import club as servicio
from app.services.errores import ErrorNegocio

router = APIRouter(prefix="/publico", tags=["sitio público"])


class DemasiadosEnvios(ErrorNegocio):
    status_code = 429


@router.get("/club", response_model=SitioOut)
def sitio(db: Session = Depends(get_db)) -> SitioOut:
    d = servicio.publico(db)
    return SitioOut(
        perfil=PerfilOut.model_validate(d["perfil"]),
        horario=[HorarioPublicoOut.model_validate(h) for h in d["horario"]],
        albumes=[AlbumOut.model_validate(a) for a in d["albumes"]],
        videos=[VideoOut.model_validate(v) for v in d["videos"]],
        equipo=[IntegranteOut.model_validate(i) for i in d["equipo"]],
        torneos=[
            TorneoPublicoOut(
                id=t.id, nombre=t.nombre, rama=t.rama, fecha_inicio=t.fecha_inicio, fecha_fin=t.fecha_fin,
                fecha_limite_inscripcion=t.fecha_limite_inscripcion, lugar=t.lugar,
                valor_inscripcion=t.valor_inscripcion, cupos_libres=libres,
            )
            for t, libres in d["torneos"]
        ],
    )


@router.get("/fotos/{foto_id}")
def foto(
    foto_id: uuid.UUID, tam: str = Query("mini", pattern="^(mini|grande)$"), db: Session = Depends(get_db),
    almacen: Almacen = Depends(get_almacen),
) -> Response:
    f = servicio.obtener_foto(db, foto_id, solo_publicada=True)
    datos = almacen.leer(f.clave_miniatura if tam == "mini" else f.clave)
    # Pública y estable (el id cambia si se reemplaza): el navegador puede guardarla un día.
    return Response(datos, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=86400"})


@router.post("/torneos/{torneo_id}/inscripcion", response_model=InscripcionSitioOut,
             status_code=status.HTTP_201_CREATED)
def inscribir_club(
    torneo_id: uuid.UUID, datos: InscripcionSitioIn, request: Request, db: Session = Depends(get_db),
) -> InscripcionSitioOut:
    ip = ip_cliente(request) or "desconocida"
    limitador = limitador_sitio()
    if limitador.segundos_bloqueo(ip):
        raise DemasiadosEnvios("Hiciste demasiados envíos seguidos. Intenta de nuevo en una hora.")
    limitador.registrar_fallo(ip)  # cuenta todo envío, válido o no
    torneo = servicio.obtener_torneo_abierto(db, torneo_id)
    if datos.sitio_web:  # trampa para bots: se responde como si nada para no darles pistas
        return InscripcionSitioOut(estado="pendiente_pago", valor=torneo.valor_inscripcion,
                                   mensaje="Recibimos la inscripción. El club te contactará.")
    equipo = servicio.inscribir_desde_sitio(
        db, torneo, datos.model_dump(exclude={"acepta_datos", "sitio_web"}), ip=ip_cliente(request)
    )
    db.commit()
    mensajes = {
        "confirmado": "¡Listo! Tu club quedó inscrito y confirmado.",
        "en_espera": "El cupo está lleno: tu club quedó en lista de espera. Te avisaremos si se libera un cupo.",
    }
    return InscripcionSitioOut(
        estado=equipo.estado, valor=equipo.valor, registrado_en=equipo.creado_en,
        mensaje=mensajes.get(equipo.estado, "Recibimos la inscripción. El club te contactará para coordinar el pago."),
    )
