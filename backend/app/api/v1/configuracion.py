from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api.deps import ip_cliente, requiere
from app.db.session import get_db
from app.models.acceso import Usuario
from app.schemas.configuracion import ConfigActualizar, ConfigOut
from app.services import configuracion as servicio

router = APIRouter(prefix="/configuracion", tags=["configuracion"])


@router.get("", response_model=list[ConfigOut])
def listar(_: Usuario = Depends(requiere("config.ver")), db: Session = Depends(get_db)) -> list[ConfigOut]:
    return [ConfigOut(clave=c.clave, valor=c.valor, descripcion=c.descripcion) for c in servicio.listar(db)]


@router.patch("/{clave}", response_model=ConfigOut)
def actualizar(
    clave: str,
    datos: ConfigActualizar,
    request: Request,
    actor: Usuario = Depends(requiere("config.editar")),
    db: Session = Depends(get_db),
) -> ConfigOut:
    try:
        fila = servicio.actualizar(db, clave=clave, valor=datos.valor, usuario_id=actor.id, ip=ip_cliente(request))
    except servicio.ConfigInvalida as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    return ConfigOut(clave=fila.clave, valor=fila.valor, descripcion=fila.descripcion)
