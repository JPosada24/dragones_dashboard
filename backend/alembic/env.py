from sqlalchemy import create_engine

import app.models  # noqa: F401  (registra todos los modelos en Base.metadata)
from alembic import context
from app.core.config import get_settings
from app.db.base import Base

target_metadata = Base.metadata
url = get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _migrar(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    # Las pruebas pueden pasar su propia conexión (p. ej. para probar una migración en una base aparte).
    propia = context.config.attributes.get("connection")
    if propia is not None:
        _migrar(propia)
        return
    engine = create_engine(url)
    with engine.connect() as connection:
        _migrar(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
