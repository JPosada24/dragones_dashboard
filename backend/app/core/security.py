"""Contraseñas (Argon2id) y tokens (JWT de acceso + refresh opaco)."""
import hashlib
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings

ALGORITMO = "HS256"

_hasher = PasswordHasher()  # Argon2id con parámetros seguros por defecto
# Hash falso: se verifica cuando el usuario no existe para que la respuesta tarde igual
# y no se pueda descubrir qué correos están registrados midiendo tiempos.
_HASH_FALSO = _hasher.hash("dragones-contrasena-falsa-1A")


def validar_politica_password(password: str) -> None:
    """Lanza ValueError si la contraseña no cumple la política mínima."""
    if len(password) < 12:
        raise ValueError("La contraseña debe tener al menos 12 caracteres.")
    if len(password) > 128:
        raise ValueError("La contraseña no puede superar 128 caracteres.")
    if not re.search(r"[a-z]", password) or not re.search(r"[A-Z]", password) or not re.search(r"\d", password):
        raise ValueError("La contraseña debe incluir mayúscula, minúscula y número.")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verificar_password(hash_guardado: str, password: str) -> bool:
    try:
        return _hasher.verify(hash_guardado, password)
    except (VerifyMismatchError, InvalidHashError, VerificationError):
        return False


def necesita_rehash(hash_guardado: str) -> bool:
    return _hasher.check_needs_rehash(hash_guardado)


def verificar_password_falso(password: str) -> None:
    verificar_password(_HASH_FALSO, password)


def crear_access_token(usuario_id: uuid.UUID, rol_codigo: str) -> tuple[str, int]:
    """Devuelve (token, segundos de vida)."""
    s = get_settings()
    ahora = datetime.now(timezone.utc)
    vida = timedelta(minutes=s.access_token_minutos)
    payload = {
        "sub": str(usuario_id),
        "rol": rol_codigo,
        "tipo": "access",
        "iat": ahora,
        "exp": ahora + vida,
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, s.secret_key, algorithm=ALGORITMO), int(vida.total_seconds())


def decodificar_access_token(token: str) -> dict:
    """Valida firma y expiración. Lanza jwt.PyJWTError si algo falla."""
    payload = jwt.decode(
        token,
        get_settings().secret_key,
        algorithms=[ALGORITMO],  # algoritmo fijo: evita ataques de "alg: none"
        options={"require": ["exp", "iat", "sub"]},
    )
    if payload.get("tipo") != "access":
        raise jwt.InvalidTokenError("Tipo de token inválido")
    return payload


def nuevo_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """En la base de datos solo se guarda el hash; el token real vive en la cookie."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
