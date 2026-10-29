"""Pruebas contra un PostgreSQL real (base "<nombre>_test", se crea sola)."""
import os
import tempfile

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

# --- Entorno de pruebas: debe fijarse ANTES de importar la aplicación ---
os.environ.setdefault("SECRET_KEY", "clave-de-pruebas-que-supera-los-32-caracteres-123")
os.environ.setdefault("DATA_ENCRYPTION_KEY", "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=")
os.environ["DOCUMENTOS_DIR"] = tempfile.mkdtemp(prefix="documentos_test_")
os.environ["ENTORNO"] = "pruebas"
os.environ["COOKIE_SECURE"] = "false"
os.environ["SUPERADMIN_EMAIL"] = ""
os.environ["SUPERADMIN_PASSWORD"] = ""
os.environ["LOGIN_FALLOS_POR_IP"] = "10"
os.environ["MAX_CUERPO_MB"] = "3"

_url = make_url(os.environ["DATABASE_URL"])
_nombre_test = f"{_url.database}_test"
_admin = create_engine(_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
with _admin.connect() as _c:
    if not _c.scalar(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": _nombre_test}):
        _c.execute(text(f'CREATE DATABASE "{_nombre_test}"'))
_admin.dispose()
os.environ["DATABASE_URL"] = _url.set(database=_nombre_test).render_as_string(hide_password=False)

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import app.models  # noqa: E402,F401  (antes de "from app.main import app": si no, "app" sería el paquete)
from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.core.limites import limitador_login  # noqa: E402
from app.main import app  # noqa: E402
from app.services import usuarios as servicio_usuarios  # noqa: E402
from app.services.catalogos import sembrar_catalogos  # noqa: E402

PASSWORD = "ClaveSegura123"


@pytest.fixture(scope="session", autouse=True)
def _esquema():
    # El esquema se construye con las migraciones reales (así también se prueban ellas y sus triggers).
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    command.upgrade(Config(str(Path(__file__).resolve().parents[1] / "alembic.ini")), "head")
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def _base_limpia():
    """Antes de cada prueba: tablas vacías y catálogos sembrados."""
    tablas = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {tablas} RESTART IDENTITY CASCADE"))
    with SessionLocal() as db:
        sembrar_catalogos(db)
    limitador_login().reiniciar()


@pytest.fixture
def db():
    with SessionLocal() as sesion:
        yield sesion


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def crear_usuario(db):
    def _crear(
        email: str, rol: str = "MIEMBRO", password: str = PASSWORD, nombre: str = "Persona Prueba", rama=None
    ):
        u = servicio_usuarios.crear_usuario(
            db, email=email, nombre=nombre, password=password, rol_codigo=rol, rama=rama
        )
        db.commit()
        return u

    return _crear


@pytest.fixture
def login(client):
    def _login(email: str, password: str = PASSWORD):
        return client.post("/api/v1/auth/login", json={"email": email, "password": password})

    return _login


@pytest.fixture
def auth_header(login):
    def _header(email: str, password: str = PASSWORD) -> dict[str, str]:
        r = login(email, password)
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return _header
