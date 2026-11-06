from typing import Any

from pydantic import BaseModel


class ConfigOut(BaseModel):
    clave: str
    valor: Any
    descripcion: str | None


class ConfigActualizar(BaseModel):
    valor: Any
