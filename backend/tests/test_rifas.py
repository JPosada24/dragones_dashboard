from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.services.rifas import huella
from tests.fabrica import (
    LUNES,
    SORTEO,
    A,
    I,
    R,
    alumno_inscrito,
    cerrar_dia,
    crear_acudiente,
    crear_alumno,
    crear_menor,
    crear_rifa,
    crear_sesion,
    en_hora,
    inscribir,
)


def _talonarios(client, h, rifa_id):
    return client.get(f"{R}/{rifa_id}/talonarios", headers=h).json()


def _pagar_talonario(client, h, rifa_id, talonario_id, monto, fecha=LUNES):
    return client.post(f"{R}/{rifa_id}/talonarios/{talonario_id}/pagos",
                       json={"monto": monto, "fecha": fecha.isoformat()}, headers=h)


def _pagar_puesto(client, h, rifa_id, numero, monto=2000, fecha=LUNES):
    return client.post(f"{R}/{rifa_id}/puestos/{numero}/pagos",
                       json={"monto": monto, "fecha": fecha.isoformat()}, headers=h)


# ---------- Creación y talonarios ----------
def test_crear_rifa_da_un_talonario_numerado_a_cada_inscrito(client, h_admin):
    a1 = alumno_inscrito(client, h_admin)
    a2 = alumno_inscrito(client, h_admin, documento="2000000003", rama="masculina")
    crear_alumno(client, h_admin, documento="2000000004")  # sin inscripción: no recibe talonario
    r = crear_rifa(client, h_admin)
    assert r.status_code == 201, r.text
    rifa = r.json()
    assert rifa["valor_talonario"] == 40000 and rifa["talonarios"] == 2 and rifa["esperado"] == 80000
    talonarios = {
        t["alumno_id"]: (t["desde"], t["hasta"], len(t["puestos"])) for t in _talonarios(client, h_admin, rifa["id"])
    }
    assert sorted(talonarios.values()) == [(0, 19, 20), (20, 39, 20)]
    assert set(talonarios) == {a1["id"], a2["id"]}


def test_asignar_talonario_a_quien_se_inscribe_despues_sigue_la_numeracion(client, h_admin):
    alumno_inscrito(client, h_admin)
    rifa = crear_rifa(client, h_admin).json()
    nueva = alumno_inscrito(client, h_admin, documento="2000000003")
    r = client.post(f"{R}/{rifa['id']}/talonarios", headers=h_admin)
    assert r.json() == {"asignados": 1}
    t = next(t for t in _talonarios(client, h_admin, rifa["id"]) if t["alumno_id"] == nueva["id"])
    assert (t["desde"], t["hasta"]) == (20, 39)
    assert client.post(f"{R}/{rifa['id']}/talonarios", headers=h_admin).json() == {"asignados": 0}


def test_maximo_de_rifas_por_anio_y_las_canceladas_no_cuentan(client, h_admin):
    for n in range(4):
        assert crear_rifa(client, h_admin, nombre=f"Rifa {n}").status_code == 201
    r = crear_rifa(client, h_admin, nombre="Rifa 5")
    assert r.status_code == 422 and "máximo" in r.json()["detail"]
    primera = client.get(R, headers=h_admin).json()[0]
    client.post(f"{R}/{primera['id']}/cancelar", json={"motivo": "Se cambió de premio"}, headers=h_admin)
    assert crear_rifa(client, h_admin, nombre="Rifa 5").json()["numero"] == 5


def test_rifa_con_fecha_pasada_o_de_otro_anio_se_rechaza(client, h_admin):
    assert crear_rifa(client, h_admin, fecha=LUNES - timedelta(days=1)).status_code == 422
    assert crear_rifa(client, h_admin, anio=2027).status_code == 422


def test_entrenador_y_miembro_no_crean_rifas_ni_registran_pagos(client, h_admin, crear_usuario, auth_header):
    alumno_inscrito(client, h_admin)
    rifa = crear_rifa(client, h_admin).json()
    crear_usuario("coach@club.com", "ENTRENADOR", rama="femenina")
    crear_usuario("m@club.com", "MIEMBRO")
    for h in (auth_header("coach@club.com"), auth_header("m@club.com")):
        assert crear_rifa(client, h).status_code == 403
        assert _pagar_puesto(client, h, rifa["id"], 0).status_code == 403
        assert client.post(f"{R}/{rifa['id']}/sorteo", headers=h).status_code == 403


# ---------- Puestos y pagos ----------
def test_registrar_comprador_y_pago_de_un_puesto(client, h_admin):
    alumno_inscrito(client, h_admin)
    rifa = crear_rifa(client, h_admin).json()
    r = client.patch(f"{R}/{rifa['id']}/puestos/3", json={"nombre": "Doña Rosa", "telefono": "300 123 4567"},
                     headers=h_admin)
    assert r.status_code == 200
    assert _pagar_puesto(client, h_admin, rifa["id"], 3, monto=1500).status_code == 200
    assert _pagar_puesto(client, h_admin, rifa["id"], 3, monto=1000).status_code == 422  # saldo 500
    puesto = _pagar_puesto(client, h_admin, rifa["id"], 3, monto=500).json()["puestos"][3]
    assert puesto["comprador_nombre"] == "Doña Rosa" and puesto["comprador_telefono"] == "3001234567"
    assert puesto["monto_pagado"] == 2000 and puesto["saldo"] == 0
    assert _pagar_puesto(client, h_admin, rifa["id"], 3, fecha=LUNES + timedelta(days=1)).status_code == 422
    assert _pagar_puesto(client, h_admin, rifa["id"], 999).status_code == 404


def test_pago_del_talonario_completo_se_reparte_entre_los_puestos(client, h_admin):
    alumno_inscrito(client, h_admin)
    rifa = crear_rifa(client, h_admin).json()
    t = _talonarios(client, h_admin, rifa["id"])[0]
    t = _pagar_talonario(client, h_admin, rifa["id"], t["id"], 25000).json()
    assert t["saldo"] == 15000 and t["pagado"] is False
    assert [p["monto_pagado"] for p in t["puestos"][:14]] == [2000] * 12 + [1000, 0]
    assert _pagar_talonario(client, h_admin, rifa["id"], t["id"], 20000).status_code == 422
    t = _pagar_talonario(client, h_admin, rifa["id"], t["id"], 15000).json()
    assert t["pagado"] is True and t["saldo"] == 0


def test_anular_un_pago_de_rifa_es_solo_del_superadmin(client, h_admin, h_root):
    alumno_inscrito(client, h_admin)
    rifa = crear_rifa(client, h_admin).json()
    pago = _pagar_puesto(client, h_admin, rifa["id"], 0).json()["puestos"][0]["pagos"][0]
    url = f"{R}/{rifa['id']}/puestos/0/pagos/{pago['id']}/anular"
    cuerpo = {"motivo": "Se registró en el puesto equivocado"}
    assert client.post(url, json=cuerpo, headers=h_admin).status_code == 403
    puesto = client.post(url, json=cuerpo, headers=h_root).json()["puestos"][0]
    assert puesto["monto_pagado"] == 0 and [p["monto"] for p in puesto["pagos"]] == [2000, -2000]
    assert client.post(url, json=cuerpo, headers=h_root).status_code == 409


def test_los_pagos_de_rifa_no_se_editan_ni_se_borran(client, h_admin, db):
    alumno_inscrito(client, h_admin)
    rifa = crear_rifa(client, h_admin).json()
    _pagar_puesto(client, h_admin, rifa["id"], 0)
    for sentencia in ("UPDATE pagos_puesto SET monto = 1", "DELETE FROM pagos_puesto"):
        with pytest.raises(DBAPIError, match="solo agregar"):
            db.execute(text(sentencia))
        db.rollback()


# ---------- Sorteo ----------
def test_sorteo_solo_entre_talonarios_pagados_y_acta_inmutable(client, h_admin, reloj, db):
    pagada = alumno_inscrito(client, h_admin)
    alumno_inscrito(client, h_admin, documento="2000000003")
    rifa = crear_rifa(client, h_admin).json()
    talonarios = {t["alumno_id"]: t for t in _talonarios(client, h_admin, rifa["id"])}
    t = talonarios[pagada["id"]]
    _pagar_talonario(client, h_admin, rifa["id"], t["id"], 40000)
    otro = next(x for x in talonarios.values() if x["id"] != t["id"])
    _pagar_talonario(client, h_admin, rifa["id"], otro["id"], 38000)  # le falta un puesto: no participa

    r = client.post(f"{R}/{rifa['id']}/sorteo", headers=h_admin)
    assert r.status_code == 422 and "aún no" in r.json()["detail"]  # antes de la fecha

    reloj(en_hora(SORTEO, 20))
    r = client.post(f"{R}/{rifa['id']}/sorteo", headers=h_admin)
    assert r.status_code == 201, r.text
    acta = r.json()
    rango = list(range(t["desde"], t["hasta"] + 1))
    assert acta["participantes"] == rango and acta["total_participantes"] == 20
    assert acta["numero_ganador"] in rango and acta["alumno_id"] == pagada["id"]
    assert acta["huella"] == huella(rango)  # cualquiera puede verificar la lista
    assert client.get(f"{R}/{rifa['id']}/acta", headers=h_admin).json() == acta
    assert client.get(f"{R}/{rifa['id']}", headers=h_admin).json()["estado"] == "sorteada"

    assert client.post(f"{R}/{rifa['id']}/sorteo", headers=h_admin).status_code == 409  # no se repite
    with pytest.raises(DBAPIError, match="solo agregar"):
        db.execute(text("UPDATE actas_sorteo SET numero_ganador = 0"))
    db.rollback()


def test_sin_talonarios_pagados_no_hay_sorteo(client, h_admin, reloj):
    alumno_inscrito(client, h_admin)
    rifa = crear_rifa(client, h_admin).json()
    reloj(en_hora(SORTEO, 20))
    r = client.post(f"{R}/{rifa['id']}/sorteo", headers=h_admin)
    assert r.status_code == 422 and "pagados" in r.json()["detail"]


def test_rifa_cancelada_no_recibe_pagos_ni_se_sortea(client, h_admin, reloj):
    alumno_inscrito(client, h_admin)
    rifa = crear_rifa(client, h_admin).json()
    client.post(f"{R}/{rifa['id']}/cancelar", json={"motivo": "Lluvia de deudas"}, headers=h_admin)
    assert _pagar_puesto(client, h_admin, rifa["id"], 0).status_code == 422
    reloj(en_hora(SORTEO, 20))
    assert client.post(f"{R}/{rifa['id']}/sorteo", headers=h_admin).status_code == 409


# ---------- Visibilidad ----------
def test_miembro_ve_solo_el_talonario_de_su_hija(client, h_admin, crear_usuario, auth_header):
    padre = crear_usuario("padre@club.com", "MIEMBRO")
    hija = crear_menor(client, h_admin, documento="3000000001",
                       acudiente=crear_acudiente(client, h_admin, usuario_id=str(padre.id)))
    inscribir(client, h_admin, hija["id"])
    alumno_inscrito(client, h_admin, documento="2000000009")
    rifa = crear_rifa(client, h_admin).json()
    assert [t["alumno_id"] for t in _talonarios(client, auth_header("padre@club.com"), rifa["id"])] == [hija["id"]]


# ---------- Estado de cuenta (paz y salvo) ----------
def test_estado_de_cuenta_suma_inscripcion_multas_y_rifas(client, h_admin, reloj, crear_usuario, auth_header):
    padre = crear_usuario("padre@club.com", "MIEMBRO")
    hija = crear_menor(client, h_admin, documento="3000000001",
                       acudiente=crear_acudiente(client, h_admin, usuario_id=str(padre.id)))
    inscripcion = inscribir(client, h_admin, hija["id"]).json()
    crear_sesion(client, h_admin)
    rifa = crear_rifa(client, h_admin).json()
    reloj(en_hora(LUNES, 23, 59))
    cerrar_dia(client, h_admin)  # una multa de $2.000

    h_padre = auth_header("padre@club.com")
    e = client.get(f"{A}/{hija['id']}/estado-cuenta", headers=h_padre).json()
    deuda_rifa = [{"rifa": rifa["nombre"], "saldo": 40000}]
    assert (e["inscripcion_saldo"], e["multas_saldo"], e["rifas"]) == (90000, 2000, deuda_rifa)
    assert e["total"] == 132000 and e["al_dia"] is False

    pago = {"fecha_pago": LUNES.isoformat(), "monto": 90000}
    client.post(f"{I}/{inscripcion['id']}/pagos", json=pago, headers=h_admin)
    multa = client.get("/api/v1/multas", headers=h_admin).json()[0]
    client.post(f"/api/v1/multas/{multa['id']}/pago", json={"fecha_pago": LUNES.isoformat()}, headers=h_admin)
    t = _talonarios(client, h_admin, rifa["id"])[0]
    _pagar_talonario(client, h_admin, rifa["id"], t["id"], 40000)
    e = client.get(f"{A}/{hija['id']}/estado-cuenta", headers=h_padre).json()
    assert e["total"] == 0 and e["al_dia"] is True

    ajena = alumno_inscrito(client, h_admin, documento="2000000009")
    assert client.get(f"{A}/{ajena['id']}/estado-cuenta", headers=h_padre).status_code == 404
