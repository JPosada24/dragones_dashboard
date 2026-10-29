"""Cifrado en reposo (Fernet: AES + HMAC) e índice ciego para buscar datos cifrados sin descifrarlos."""
import base64
import hashlib
import hmac
from functools import lru_cache

from cryptography.fernet import Fernet

from app.core.config import get_settings


@lru_cache
def _fernet() -> Fernet:
    return Fernet(get_settings().data_encryption_key.encode())


@lru_cache
def _clave_indice() -> bytes:
    # Subclave derivada: el índice no usa directamente la misma clave que el cifrado.
    raiz = base64.urlsafe_b64decode(get_settings().data_encryption_key)
    return hmac.new(raiz, b"dragones-indice-ciego-v1", hashlib.sha256).digest()


def cifrar(texto: str) -> bytes:
    return _fernet().encrypt(texto.encode("utf-8"))


def descifrar(dato: bytes) -> str:
    return _fernet().decrypt(dato).decode("utf-8")


def cifrar_bytes(datos: bytes) -> bytes:
    return _fernet().encrypt(datos)


def descifrar_bytes(datos: bytes) -> bytes:
    return _fernet().decrypt(datos)


def indice_ciego(valor: str) -> str:
    """HMAC determinístico: el mismo valor da el mismo índice, pero no se puede revertir sin la clave."""
    return hmac.new(_clave_indice(), valor.encode("utf-8"), hashlib.sha256).hexdigest()
