import logging

import anthropic
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import requiere
from app.core.config import get_settings
from app.db.session import get_db
from app.models.acceso import Usuario
from app.schemas.agente import EstadoAgenteOut, PreguntaIn, RespuestaOut
from app.services import agente as servicio

router = APIRouter(prefix="/agente", tags=["agente"])
log = logging.getLogger(__name__)
USAR = requiere("agente.usar")


def get_ia() -> anthropic.Anthropic:
    """Cliente de la API de Claude (las pruebas lo reemplazan por uno falso)."""
    return servicio.cliente()


@router.get("/estado", response_model=EstadoAgenteOut)
def estado(usuario: Usuario = Depends(USAR), db: Session = Depends(get_db)) -> EstadoAgenteOut:
    return EstadoAgenteOut(
        configurado=bool(get_settings().anthropic_api_key), limite_diario=servicio.limite_diario(db),
        usados_hoy=servicio.usados_hoy(db, usuario),
    )


@router.post("/preguntar", response_model=RespuestaOut)
def preguntar(
    datos: PreguntaIn,
    usuario: Usuario = Depends(USAR),
    db: Session = Depends(get_db),
    ia: anthropic.Anthropic = Depends(get_ia),
) -> RespuestaOut:
    try:
        r = servicio.preguntar(
            db, usuario, [m.model_dump() for m in datos.historial], datos.pregunta, ia=ia
        )
    except anthropic.APIError as e:
        # Sin el contenido de la conversación en el log (puede traer datos de menores).
        log.warning("Fallo de la API de Claude: %s", type(e).__name__)
        raise servicio.AgenteNoDisponible("El asistente no respondió. Intenta de nuevo en un momento.") from e
    return RespuestaOut(texto=r.texto, herramientas=r.herramientas, restantes_hoy=r.restantes_hoy)
