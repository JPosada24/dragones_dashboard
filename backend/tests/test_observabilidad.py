"""Identificador por petición y limpieza de los errores que se reportan a Sentry/GlitchTip."""
from app.core.observabilidad import limpiar_evento


def test_cada_respuesta_lleva_su_identificador(client):
    r = client.get("/api/v1/salud")
    assert len(r.headers["x-request-id"]) == 32
    assert client.get("/api/v1/salud").headers["x-request-id"] != r.headers["x-request-id"]


def test_se_respeta_el_identificador_del_proxy_pero_no_cualquier_texto(client):
    propio = client.get("/api/v1/salud", headers={"X-Request-ID": "caddy-1234abcd"})
    assert propio.headers["x-request-id"] == "caddy-1234abcd"
    inyectado = client.get("/api/v1/salud", headers={"X-Request-ID": "x\nnivel=ERROR falso"})
    assert inyectado.headers["x-request-id"] != "x\nnivel=ERROR falso"  # no se copia a los logs lo que mande el cliente


def test_al_reportar_un_error_no_salen_sesion_cuerpos_ni_usuario():
    evento = {
        "request": {
            "headers": {"Authorization": "Bearer abc", "Cookie": "refresh=xyz", "User-Agent": "Firefox"},
            "data": {"documento": "1098765432"},
            "cookies": {"refresh": "xyz"},
            "query_string": "buscar=1098765432",
        },
        "user": {"email": "marta@club.com"},
    }
    limpio = limpiar_evento(evento)
    cabeceras = limpio["request"]["headers"]
    assert cabeceras == {"Authorization": "[filtrado]", "Cookie": "[filtrado]", "User-Agent": "Firefox"}
    assert "data" not in limpio["request"] and "cookies" not in limpio["request"]
    assert "query_string" not in limpio["request"] and "user" not in limpio
