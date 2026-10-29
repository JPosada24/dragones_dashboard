import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.sistema import Auditoria


def registrar(
    db: Session,
    *,
    accion: str,
    entidad: str,
    usuario_id: uuid.UUID | None = None,
    entidad_id: str | None = None,
    antes: Any | None = None,
    despues: Any | None = None,
    ip: str | None = None,
) -> None:
    """Agrega una fila a la bitácora. No hace commit: lo hace quien llama, en la misma transacción."""
    db.add(
        Auditoria(
            usuario_id=usuario_id,
            accion=accion,
            entidad=entidad,
            entidad_id=entidad_id,
            antes=antes,
            despues=despues,
            ip=ip,
        )
    )
