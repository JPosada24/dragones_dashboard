"""Solicitudes de habeas data: plazos en días hábiles, prórroga única, respuesta, permisos y alerta."""
from datetime import date

from sqlalchemy import select

from app.models.sistema import Auditoria
from app.services.habeas import habiles_entre, sumar_habiles

H = "/api/v1/habeas"
CONSULTA = {"tipo": "consulta", "titular": "Marta Gómez", "contacto": "marta@correo.com",
            "descripcion": "Quiero saber qué datos tienen de mi hija Laura.", "recibida_el": "2026-11-02"}


def test_dias_habiles_saltan_fines_de_semana_y_festivos():
    # Desde el 2 nov 2026 (festivo) + 10 hábiles; el 16 también es festivo (Independencia de Cartagena, trasladado).
    assert sumar_habiles(date(2026, 11, 2), 10) == date(2026, 11, 17)
    assert habiles_entre(date(2026, 11, 13), date(2026, 11, 17)) == 1  # viernes → martes, con el lunes festivo
    assert habiles_entre(date(2026, 11, 18), date(2026, 11, 17)) == -1


def test_registrar_prorrogar_una_vez_y_responder(client, h_root, db):
    r = client.post(H, json=CONSULTA, headers=h_root)
    assert r.status_code == 201, r.text
    s = r.json()
    assert s["vence_el"] == "2026-11-17" and s["estado"] == "en_tramite"

    p = client.post(f"{H}/{s['id']}/prorrogar", json={"motivo": "Hay que revisar el archivo físico."}, headers=h_root)
    assert p.status_code == 200 and p.json()["vence_el"] == "2026-11-24" and p.json()["prorrogada"] is True
    otra = client.post(f"{H}/{s['id']}/prorrogar", json={"motivo": "Otra vez por si acaso."}, headers=h_root)
    assert otra.status_code == 422 and "una vez" in otra.json()["detail"]

    url = f"{H}/{s['id']}/responder"
    resp = client.post(url, json={"respuesta": "Le enviamos sus datos al correo."}, headers=h_root)
    assert resp.status_code == 200 and resp.json()["estado"] == "respondida"
    assert client.post(url, json={"respuesta": "Segunda respuesta."}, headers=h_root).status_code == 422
    # El texto (posibles datos personales) no va a la auditoría.
    for a in db.scalars(select(Auditoria).where(Auditoria.entidad == "solicitud_datos")):
        assert "Laura" not in str(a.despues) and "correo" not in str(a.despues)


def test_un_reclamo_tiene_15_dias_habiles(client, h_root):
    r = client.post(H, json={**CONSULTA, "tipo": "reclamo", "descripcion": "Corrijan el teléfono del acudiente."},
                    headers=h_root)
    assert r.json()["vence_el"] == str(sumar_habiles(date(2026, 11, 2), 15))


def test_solo_el_superadmin_gestiona_solicitudes(client, h_admin):
    assert client.get(H, headers=h_admin).status_code == 403
    assert client.post(H, json=CONSULTA, headers=h_admin).status_code == 403


def test_alerta_en_el_resumen_cuando_esta_por_vencer(client, h_root, reloj):
    from tests.fabrica import en_hora

    client.post(H, json=CONSULTA, headers=h_root)
    reloj(en_hora(date(2026, 11, 12), 9))  # faltan 2 hábiles: el 13 y el 17 (el 16 es festivo)
    alertas = client.get("/api/v1/resumen", headers=h_root).json()["alertas"]
    assert any(a["tipo"] == "habeas" and a["ruta"] == "/habeas" for a in alertas)
