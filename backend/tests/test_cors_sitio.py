"""El sitio público (otro dominio) solo puede usar /api/v1/publico, y nunca con credenciales."""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.cors import CorsSitio

SITIO = "https://club-dragones.example"


def _cliente() -> TestClient:
    app = FastAPI()

    @app.get("/api/v1/publico/club")
    def club() -> dict:
        return {"ok": True}

    @app.get("/api/v1/alumnos")
    def alumnos() -> dict:
        return {"ok": True}

    app.add_middleware(CorsSitio, origenes=[SITIO])
    return TestClient(app)


def test_el_sitio_lee_lo_publico_sin_credenciales():
    r = _cliente().get("/api/v1/publico/club", headers={"Origin": SITIO})
    assert r.headers["access-control-allow-origin"] == SITIO
    assert "access-control-allow-credentials" not in r.headers


def test_preflight_solo_get_y_post():
    r = _cliente().options("/api/v1/publico/club", headers={
        "Origin": SITIO, "Access-Control-Request-Method": "POST"})
    assert r.status_code == 204 and r.headers["access-control-allow-methods"] == "GET, POST"


def test_ni_rutas_privadas_ni_otros_origenes():
    c = _cliente()
    assert "access-control-allow-origin" not in c.get("/api/v1/alumnos", headers={"Origin": SITIO}).headers
    otro = c.get("/api/v1/publico/club", headers={"Origin": "https://malo.example"})
    assert "access-control-allow-origin" not in otro.headers
