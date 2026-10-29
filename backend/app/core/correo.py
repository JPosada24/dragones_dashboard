"""Envío de correo detrás de una interfaz: hoy SMTP (p. ej. Gmail con contraseña de aplicación) o "registro".

En modo registro no sale nada: solo se anota (desarrollo, pruebas o mientras no se configure la cuenta).
"""
import logging
import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings

log = logging.getLogger("dragones.correo")


class Correo(Protocol):
    def enviar(self, destino: str, asunto: str, cuerpo: str) -> None: ...


def _mensaje(remitente: str, destino: str, asunto: str, cuerpo: str) -> EmailMessage:
    # EmailMessage rechaza saltos de línea en las cabeceras: no hay inyección de cabeceras posible.
    msg = EmailMessage()
    msg["From"] = remitente
    msg["To"] = destino
    msg["Subject"] = asunto
    msg.set_content(cuerpo)
    return msg


@dataclass
class CorreoSMTP:
    host: str
    puerto: int
    usuario: str
    password: str
    remitente: str
    seguridad: str = "starttls"  # starttls (puerto 587) | ssl (puerto 465)

    def enviar(self, destino: str, asunto: str, cuerpo: str) -> None:
        msg = _mensaje(self.remitente, destino, asunto, cuerpo)
        contexto = ssl.create_default_context()  # verifica el certificado del servidor
        if self.seguridad == "ssl":
            with smtplib.SMTP_SSL(self.host, self.puerto, context=contexto, timeout=20) as s:
                s.login(self.usuario, self.password)
                s.send_message(msg)
        else:
            with smtplib.SMTP(self.host, self.puerto, timeout=20) as s:
                s.starttls(context=contexto)
                s.login(self.usuario, self.password)
                s.send_message(msg)


class CorreoRegistro:
    """No envía: guarda lo que habría enviado. Las pruebas lo leen en `enviados`."""

    def __init__(self) -> None:
        self.enviados: list[tuple[str, str, str]] = []

    def enviar(self, destino: str, asunto: str, cuerpo: str) -> None:
        _mensaje("registro@localhost", destino, asunto, cuerpo)  # mismas validaciones que el envío real
        self.enviados.append((destino, asunto, cuerpo))
        usuario, _, dominio = destino.partition("@")
        log.info("Correo en modo registro (no enviado) para %s***@%s: %s", usuario[:2], dominio, asunto)


@lru_cache
def correo_registro() -> CorreoRegistro:
    return CorreoRegistro()


def get_correo() -> Correo:
    s = get_settings()
    if s.email_modo == "smtp":
        return CorreoSMTP(
            host=s.smtp_host, puerto=s.smtp_puerto, usuario=s.smtp_usuario, password=s.smtp_password,
            remitente=s.smtp_remitente, seguridad=s.smtp_seguridad,
        )
    return correo_registro()
