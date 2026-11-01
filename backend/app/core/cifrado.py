"""Cifrado en reposo (Fernet: AES + HMAC) e índice ciego para buscar datos cifrados sin descifrarlos.

`DATA_ENCRYPTION_KEY` admite varias claves separadas por comas: la **primera** cifra y todas descifran. Para rotar:
poner la nueva delante ("nueva,vieja"), correr `python -m app.scripts.rotar_clave` (vuelve a cifrar todo con la
nueva) y después dejar solo la nueva. Ver docs/operacion.md.
"""
import base64
import hashlib
import hmac
from functools import lru_cache

from cryptography.fernet import Fernet, MultiFernet

from app.core.config import get_settings


def _claves() -> list[str]:
    claves = [c.strip() for c in get_settings().data_encryption_key.split(",") if c.strip()]
    if not claves:
        raise RuntimeError("DATA_ENCRYPTION_KEY está vacía")
    return claves


@lru_cache
def _fernet() -> MultiFernet:
    return MultiFernet([Fernet(c.encode()) for c in _claves()])


@lru_cache
def _clave_indice() -> bytes:
    # Subclave derivada de la clave vigente: el índice no usa directamente la misma clave que el cifrado.
    raiz = base64.urlsafe_b64decode(_claves()[0])
    return hmac.new(raiz, b"dragones-indice-ciego-v1", hashlib.sha256).digest()


def reiniciar_claves() -> None:
    """Olvida las claves en caché (tras cambiar la configuración: rotación y pruebas)."""
    _fernet.cache_clear()
    _clave_indice.cache_clear()


def cifrar(texto: str) -> bytes:
    return _fernet().encrypt(texto.encode("utf-8"))


def descifrar(dato: bytes) -> str:
    return _fernet().decrypt(dato).decode("utf-8")


def cifrar_bytes(datos: bytes) -> bytes:
    return _fernet().encrypt(datos)


def descifrar_bytes(datos: bytes) -> bytes:
    return _fernet().decrypt(datos)


def recifrar(dato: bytes) -> bytes:
    """Descifra con la clave que corresponda y vuelve a cifrar con la vigente (rotación)."""
    return _fernet().rotate(dato)


def indice_ciego(valor: str) -> str:
    """HMAC determinístico: el mismo valor da el mismo índice, pero no se puede revertir sin la clave."""
    return hmac.new(_clave_indice(), valor.encode("utf-8"), hashlib.sha256).hexdigest()
