"""Demo público: qué no se permite, la ruta /demo y el generador del club ficticio."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.demo import CLAVE_DEMO, CUENTAS_DEMO, motivo_bloqueo
from app.main import crear_app
from app.models.acceso import Usuario
from app.models.alumnos import Acudiente, Alumno
from app.models.asistencia import Asistencia
from app.models.torneos import Torneo
from app.scripts import demo as script


@pytest.fixture
def modo_demo(monkeypatch):
    monkeypatch.setattr(get_settings(), "demo", True)


def test_fuera_del_demo_no_existe_la_ruta(client):
    assert client.get("/api/v1/demo").status_code == 404


@pytest.mark.parametrize(("metodo", "ruta", "tipo", "bloqueada"), [
    ("POST", "/api/v1/usuarios", "application/json", True),
    ("PATCH", "/api/v1/usuarios/1", "application/json", True),
    ("PUT", "/api/v1/usuarios/1/permisos", "application/json", True),
    ("GET", "/api/v1/usuarios", "", False),
    ("POST", "/api/v1/alumnos/1/documentos", "multipart/form-data; boundary=x", True),
    ("POST", "/api/v1/alumnos", "application/json", False),
    ("POST", "/api/v1/auth/login", "application/json", False),
])
def test_que_no_se_permite_en_el_demo(metodo, ruta, tipo, bloqueada):
    assert (motivo_bloqueo(metodo, ruta, tipo) is not None) is bloqueada


def test_en_el_demo_se_ven_las_cuentas_y_no_se_tocan_usuarios_ni_archivos(modo_demo, db, crear_usuario, auth_header):
    cliente = TestClient(crear_app())
    d = cliente.get("/api/v1/demo").json()
    assert d["clave"] == CLAVE_DEMO and [c["rol"] for c in d["cuentas"]] == [r for r, _, _ in CUENTAS_DEMO]
    crear_usuario("dueno@club.com", "SUPERADMIN")
    h = auth_header("dueno@club.com")
    r = cliente.post("/api/v1/usuarios", json={"email": "x@club.com"}, headers=h)
    assert r.status_code == 403 and "cuentas" in r.json()["detail"]
    r = cliente.post("/api/v1/club/albumes/1/fotos", files={"archivo": ("f.jpg", b"x", "image/jpeg")}, headers=h)
    assert r.status_code == 403 and "archivos" in r.json()["detail"]
    assert cliente.get("/api/v1/usuarios", headers=h).status_code == 200


def test_en_el_demo_el_tutorial_sale_en_cada_ingreso(modo_demo, client, crear_usuario, auth_header):
    crear_usuario("admin@club.com", "ADMIN")
    h = auth_header("admin@club.com")
    assert client.post("/api/v1/auth/tutorial", headers=h).status_code == 204
    assert client.get("/api/v1/auth/me", headers=h).json()["tutorial_visto"] is False


def test_el_generador_no_corre_fuera_del_demo():
    with pytest.raises(SystemExit, match="solo corre en el demo"):
        script.generar()


def test_el_generador_arma_un_club_completo_con_las_reglas_reales(modo_demo, monkeypatch, db):
    # Dos semanas: con una sola, un festivo y el día del torneo pueden dejarla sin entrenamientos.
    monkeypatch.setattr(script, "SEMANAS", 2)
    script.generar(semilla=7)
    assert db.scalar(select(func.count()).select_from(Alumno)) >= 30  # los que llegan después de hoy no entran
    assert db.scalar(select(func.count()).select_from(Asistencia)) > 0
    assert db.scalar(select(func.count()).select_from(Torneo)) == 2
    cliente = TestClient(crear_app())
    for _, email, _ in CUENTAS_DEMO:  # las cuentas de prueba entran con la clave pública
        r = cliente.post("/api/v1/auth/login", json={"email": email, "password": CLAVE_DEMO})
        assert r.status_code == 200, email
    # Solo staff: sin cuentas de familia ni acudientes (alumnos mayores de edad).
    assert {r for r, _, _ in CUENTAS_DEMO} == {"SUPERADMIN", "ADMIN", "ENTRENADOR"}
    assert db.scalar(select(func.count()).select_from(Acudiente)) == 0
    assert db.scalar(select(func.count()).select_from(Usuario).where(Usuario.nombre.ilike("%julian%"))) == 0
