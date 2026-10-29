"""Configuración de la aplicación, leída de variables de entorno (o de .env)."""
from functools import lru_cache

from cryptography.fernet import Fernet
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    entorno: str = "desarrollo"  # desarrollo | pruebas | produccion
    database_url: str
    secret_key: str = Field(min_length=32)

    access_token_minutos: int = 15
    refresh_token_dias: int = 7
    cookie_secure: bool = False
    cors_origins: str = "http://localhost:4200"

    max_intentos_login: int = 5
    bloqueo_minutos: int = 15
    # Límite por IP (además del bloqueo por cuenta): fallos de login permitidos por ventana.
    login_fallos_por_ip: int = 30
    login_ventana_minutos: int = 15
    # Tope duro del tamaño de cualquier petición (MB). Gana sobre "documento_max_mb" de la configuración.
    max_cuerpo_mb: int = 25

    # Worker (python -m app.worker): cada cuánto corre cada tarea programada.
    worker_cierre_segundos: int = 300  # el cierre de las 23:59 ocurre, a más tardar, 5 min después
    worker_vencer_segundos: int = 3600
    worker_notificaciones_segundos: int = 3600
    worker_correos_segundos: int = 60

    # Correo. "registro" = no envía nada (solo lo anota). "smtp" = envía con la cuenta de abajo.
    club_nombre: str = "Club Dragones"
    email_modo: str = "registro"  # registro | smtp
    smtp_host: str = "smtp.gmail.com"
    smtp_puerto: int = 587
    smtp_seguridad: str = "starttls"  # starttls | ssl
    smtp_usuario: str | None = None
    smtp_password: str | None = None  # en Gmail: "contraseña de aplicación", nunca la clave normal
    smtp_remitente: str | None = None

    @model_validator(mode="after")
    def _validar_correo(self) -> "Settings":
        if self.email_modo not in ("registro", "smtp"):
            raise ValueError("EMAIL_MODO debe ser 'registro' o 'smtp'.")
        if self.email_modo == "smtp" and not (self.smtp_usuario and self.smtp_password and self.smtp_remitente):
            raise ValueError("Con EMAIL_MODO=smtp hay que definir SMTP_USUARIO, SMTP_PASSWORD y SMTP_REMITENTE.")
        if self.smtp_seguridad not in ("starttls", "ssl"):
            raise ValueError("SMTP_SEGURIDAD debe ser 'starttls' o 'ssl'.")
        return self

    superadmin_email: str | None = None
    superadmin_password: str | None = None
    superadmin_nombre: str = "Administrador"

    # Clave Fernet para cifrar en reposo (documentos de identidad y archivos). Si se pierde, esos datos no se recuperan.
    data_encryption_key: str
    documentos_dir: str = "/data/documentos"

    @field_validator("data_encryption_key")
    @classmethod
    def _validar_clave_cifrado(cls, v: str) -> str:
        try:
            Fernet(v.encode())
        except (ValueError, TypeError):
            raise ValueError(
                "DATA_ENCRYPTION_KEY inválida. Genera una con: "
                'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            )
        return v

    @property
    def es_produccion(self) -> bool:
        return self.entorno == "produccion"

    @property
    def cors_lista(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def _validar_produccion(self) -> "Settings":
        if self.es_produccion:
            if not self.cookie_secure:
                raise ValueError("En producción COOKIE_SECURE debe ser true (HTTPS).")
            if "CAMBIA" in self.secret_key.upper():
                raise ValueError("En producción SECRET_KEY no puede ser el valor de ejemplo.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
