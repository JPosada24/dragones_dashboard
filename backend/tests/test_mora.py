from datetime import date, timedelta

import pytest

from app import worker
from app.core.fechas import sumar_meses
from tests.fabrica import LUNES, A, I, M, alumno_inscrito, cerrar_dia, crear_rifa, crear_sesion, en_hora

MO = "/api/v1/mora"
N = "/api/v1/notificaciones"
EN_MORA = sumar_meses(LUNES, 3)  # 02/02/2027


def _tarea():
    return next(t for t in worker.tareas() if t.nombre == "mora")


def _inscripcion(client, h, alumno_id):
    return client.get(I, params={"alumno_id": alumno_id}, headers=h).json()[0]


@pytest.fixture
def con_multa(client, h_admin, familia, reloj):
    """La hija paga su inscripción (queda activa) pero tiene una multa del lunes sin pagar."""
    hija = familia["hija"]
    i = _inscripcion(client, h_admin, hija["id"])
    client.post(f"{I}/{i['id']}/pagos", json={"fecha_pago": LUNES.isoformat(), "monto": 90000}, headers=h_admin)
    crear_sesion(client, h_admin)
    reloj(en_hora(LUNES, 23, 59))
    cerrar_dia(client, h_admin)
    return hija


def test_sumar_meses_respeta_el_fin_de_mes():
    assert sumar_meses(date(2027, 1, 31), 1) == date(2027, 2, 28)
    assert sumar_meses(date(2028, 1, 31), 1) == date(2028, 2, 29)
    assert sumar_meses(date(2026, 11, 2), 3) == date(2027, 2, 2)


def test_aviso_a_la_familia_15_dias_antes_de_la_mora(client, familia, con_multa, reloj):
    reloj(en_hora(EN_MORA - timedelta(days=16), 9))
    assert worker.ejecutar(_tarea()) is None
    reloj(en_hora(EN_MORA - timedelta(days=15), 9))
    assert worker.ejecutar(_tarea()) == "0 a expulsar, 0 expulsados, 0 al día, 1 avisos de mora"
    assert worker.ejecutar(_tarea()) is None  # no se repite
    aviso = next(a for a in client.get(f"{N}/mias", headers=familia["h"]).json() if a["tipo"] == "aviso_mora")
    assert "02/02/2027" in aviso["mensaje"] and "$2.000" in aviso["mensaje"]


def test_con_tres_meses_de_deuda_pasa_a_expulsar_y_avisa(client, h_admin, familia, con_multa, reloj):
    reloj(en_hora(EN_MORA - timedelta(days=1), 9))
    worker.ejecutar(_tarea())
    assert _inscripcion(client, h_admin, con_multa["id"])["estado"] == "activo"

    reloj(en_hora(EN_MORA, 9))
    assert worker.ejecutar(_tarea()) == "1 a expulsar, 0 expulsados, 0 al día, 0 avisos de mora"
    assert worker.ejecutar(_tarea()) is None
    i = _inscripcion(client, h_admin, con_multa["id"])
    assert i["estado"] == "a_expulsar" and "Mora" in i["motivo"]

    assert "mora" in {a["tipo"] for a in client.get(f"{N}/mias", headers=familia["h"]).json()}
    assert "mora_staff" in {a["tipo"] for a in client.get(f"{N}/mias", headers=h_admin).json()}
    [riesgo] = client.get(MO, headers=h_admin).json()
    assert riesgo["en_mora"] is True and riesgo["total_vencido"] == 2000
    cuenta = client.get(f"{A}/{con_multa['id']}/estado-cuenta", headers=familia["h"]).json()
    assert cuenta["en_mora"] is True and cuenta["entra_en_mora"] == EN_MORA.isoformat()


def test_al_ponerse_al_dia_vuelve_a_activo(client, h_admin, familia, con_multa, reloj):
    reloj(en_hora(EN_MORA, 9))
    worker.ejecutar(_tarea())
    multa = client.get(M, headers=h_admin).json()[0]
    client.post(f"{M}/{multa['id']}/pago", json={"fecha_pago": EN_MORA.isoformat()}, headers=h_admin)
    assert worker.ejecutar(_tarea()) == "0 a expulsar, 0 expulsados, 1 al día, 0 avisos de mora"
    i = _inscripcion(client, h_admin, con_multa["id"])
    assert i["estado"] == "activo" and i["causa_expulsion"] is None
    assert "fin_mora" in {a["tipo"] for a in client.get(f"{N}/mias", headers=familia["h"]).json()}


def test_con_expulsion_automatica_queda_expulsado(client, h_root, h_admin, con_multa, reloj):
    client.patch("/api/v1/configuracion/expulsion_automatica", json={"valor": True}, headers=h_root)
    reloj(en_hora(EN_MORA, 9))
    assert worker.ejecutar(_tarea()) == "0 a expulsar, 1 expulsados, 0 al día, 0 avisos de mora"
    assert _inscripcion(client, h_admin, con_multa["id"])["estado"] == "expulsado"


def test_lo_marcado_a_mano_no_lo_revierte_el_sistema(client, h_admin, familia, reloj):
    i = _inscripcion(client, h_admin, familia["hija"]["id"])
    client.post(f"{I}/{i['id']}/pagos", json={"fecha_pago": LUNES.isoformat(), "monto": 90000}, headers=h_admin)
    client.post(f"{I}/{i['id']}/estado", json={"estado": "a_expulsar", "motivo": "Indisciplina grave"},
                headers=h_admin)
    assert worker.ejecutar(_tarea()) is None  # no tiene deudas, pero la decisión fue manual
    i = _inscripcion(client, h_admin, familia["hija"]["id"])
    assert i["estado"] == "a_expulsar" and i["causa_expulsion"] == "manual"


def test_el_talonario_se_debe_desde_el_sorteo(client, h_admin, reloj):
    alumna = alumno_inscrito(client, h_admin)
    i = _inscripcion(client, h_admin, alumna["id"])
    client.post(f"{I}/{i['id']}/pagos", json={"fecha_pago": LUNES.isoformat(), "monto": 90000}, headers=h_admin)
    sorteo = LUNES + timedelta(days=10)
    crear_rifa(client, h_admin, fecha=sorteo)
    assert client.get(MO, headers=h_admin).json() == []  # antes del sorteo aún no se debe
    reloj(en_hora(sorteo, 9))
    [riesgo] = client.get(MO, headers=h_admin).json()
    assert riesgo["total_vencido"] == 40000 and riesgo["entra_en_mora"] == sumar_meses(sorteo, 3).isoformat()
    reloj(en_hora(sumar_meses(sorteo, 3), 9))
    worker.ejecutar(_tarea())
    assert _inscripcion(client, h_admin, alumna["id"])["estado"] == "a_expulsar"


def test_la_lista_de_mora_respeta_roles(client, h_admin, con_multa, crear_usuario, auth_header, familia):
    assert client.get(MO, headers=familia["h"]).status_code == 403
    crear_usuario("coach_m@club.com", "ENTRENADOR", rama="masculina")
    crear_usuario("coach_f@club.com", "ENTRENADOR", rama="femenina")
    assert client.get(MO, headers=auth_header("coach_m@club.com")).json() == []
    assert len(client.get(MO, headers=auth_header("coach_f@club.com")).json()) == 1
