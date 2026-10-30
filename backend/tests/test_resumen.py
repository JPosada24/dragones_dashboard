from datetime import timedelta

from tests.fabrica import I
from tests.test_asistencia import (  # noqa: F401  (reloj, familia, h_admin y h_root son fixtures)
    LUNES, _alumno_inscrito, _en, _justificar, _marcar, _sesion, familia, h_admin, h_root, reloj,
)
from tests.test_rifas import _rifa
from tests.test_torneos import _equipo, _torneo

RES = "/api/v1/resumen"


def test_indicadores_cartera_y_entrenamiento_de_hoy(client, h_admin, reloj):
    presente = _alumno_inscrito(client, h_admin)
    _alumno_inscrito(client, h_admin, documento="2000000003")  # no marca
    _alumno_inscrito(client, h_admin, documento="2000000004", rama="masculina")
    sesion = _sesion(client, h_admin)
    _marcar(client, h_admin, sesion["id"], (presente["id"], "presente"))
    _rifa(client, h_admin)

    r = client.get(RES, headers=h_admin).json()
    ind = r["indicadores"]
    assert ind["alumnos_activos"] == 3 and ind["inscripciones_pendientes"] == 3
    assert ind["inscripciones_vencen_pronto"] == 0  # el plazo es de 30 días
    [hoy] = r["hoy"]
    assert (hoy["esperados"], hoy["presentes"], hoy["sin_marcar"]) == (3, 1, 2)  # general: ambas ramas
    cartera = {c["concepto"]: c["monto"] for c in r["cartera"]}
    assert cartera["Inscripciones por cobrar"] == 3 * 90000
    assert cartera["Rifas por cobrar"] == 3 * 40000
    [rifa] = r["rifas"]
    assert (rifa["talonarios"], rifa["pagados"]) == (3, 0)


def test_alertas_que_requieren_decision(client, h_admin, h_root, familia, reloj):
    hija = familia["hija"]
    sesion = _sesion(client, h_admin)
    _justificar(client, familia["h"], sesion["id"], hija["id"])
    otra = _alumno_inscrito(client, h_admin, documento="2000000005")
    i = client.get(I, params={"alumno_id": otra["id"]}, headers=h_admin).json()[0]
    client.post(f"{I}/{i['id']}/pagos", json={"fecha_pago": LUNES.isoformat(), "monto": 90000}, headers=h_admin)
    client.post(f"{I}/{i['id']}/estado", json={"estado": "a_expulsar", "motivo": "Indisciplina grave"}, headers=h_admin)

    reloj(_en(LUNES + timedelta(days=25), 9))  # a la hija le faltan 5 días para pagar
    alertas = client.get(RES, headers=h_root).json()["alertas"]
    tipos = [a["tipo"] for a in alertas]
    assert tipos[0] == "expulsion"  # lo más urgente primero
    assert {"justificaciones", "vence_inscripcion"} <= set(tipos)
    vence = next(a for a in alertas if a["tipo"] == "vence_inscripcion")
    assert vence["cuando"] == "en 5 d" and vence["ruta"] == "/inscripciones"


def test_entrenador_ve_solo_su_rama_y_sin_torneos(client, h_admin, crear_usuario, auth_header):
    _alumno_inscrito(client, h_admin)
    _alumno_inscrito(client, h_admin, documento="2000000004", rama="masculina")
    _sesion(client, h_admin)
    _torneo(client, h_admin)
    crear_usuario("coach@club.com", "ENTRENADOR", rama="femenina")
    r = client.get(RES, headers=auth_header("coach@club.com")).json()
    assert r["indicadores"]["alumnos_activos"] == 1
    assert r["hoy"][0]["esperados"] == 1 and r["proximo_torneo"] is None  # la sesión es general; cuenta su rama
    assert "Torneos por cobrar" not in {c["concepto"] for c in r["cartera"]}


def test_proximo_torneo_y_su_cartera(client, h_admin):
    torneo = _torneo(client, h_admin).json()
    _equipo(client, h_admin, torneo["id"])
    r = client.get(RES, headers=h_admin).json()
    assert r["proximo_torneo"]["ocupados"] == 1 and r["proximo_torneo"]["cupo"] == 18
    assert {c["concepto"]: c["monto"] for c in r["cartera"]}["Torneos por cobrar"] == 150000


def test_las_familias_no_ven_el_tablero_del_staff(client, familia):
    assert client.get(RES, headers=familia["h"]).status_code == 403
