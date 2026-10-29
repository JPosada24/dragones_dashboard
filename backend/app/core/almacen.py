"""Almacenamiento de archivos. Hoy en disco (volumen de Docker); la interfaz permite pasar a S3 sin tocar el resto."""
import os
import re
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings


class Almacen(Protocol):
    def guardar(self, clave: str, datos: bytes) -> None: ...
    def leer(self, clave: str) -> bytes: ...
    def borrar(self, clave: str) -> None: ...


class AlmacenLocal:
    def __init__(self, raiz: str | Path) -> None:
        self.raiz = Path(raiz)

    def _ruta(self, clave: str) -> Path:
        # La clave la genera el servidor (uuid hex); se valida igual para impedir rutas tipo "../".
        if not re.fullmatch(r"[0-9a-f]{32}", clave):
            raise ValueError("Clave de almacenamiento inválida")
        return self.raiz / clave[:2] / clave

    def guardar(self, clave: str, datos: bytes) -> None:
        ruta = self._ruta(clave)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        temporal = ruta.with_suffix(".tmp")
        temporal.write_bytes(datos)
        os.replace(temporal, ruta)  # escritura atómica: nunca queda un archivo a medias

    def leer(self, clave: str) -> bytes:
        return self._ruta(clave).read_bytes()

    def borrar(self, clave: str) -> None:
        self._ruta(clave).unlink(missing_ok=True)


def get_almacen() -> Almacen:
    return AlmacenLocal(get_settings().documentos_dir)
