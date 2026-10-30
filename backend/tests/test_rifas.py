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


# ---------- Creación y talonarios ----------
def test_crear_rifa_da_un_talonario_a_cada_inscrito(client, h_admin):
    a1 = alumno_inscrito(client, h_admin)
    a2 = alumno_inscrito(client, h_admin, documento="2000000003", rama="masculina")
    crear_alumno(client, h_admin, documento="2000000004")  # sin inscripción: no recibe talonario
    r = crear_rifa(client, h_admin)
    assert r.status_code == 201, r.text
    rifa = r.json()
    assert rifa["valor_talonario"] == 40000 and rifa["talonarios"] == 2 and rifa["esperado"] == 80000
    talonarios = {t["alumno_id"]: (t["codigo"], t["boletas"]) for t in _talonarios(client, h_admin, rifa["id"])}
    assert talonarios == {a1["id"]: (a1["codigo"], 20), a2["id"]: (a2["codigo"], 20)}


def test_asignar_talonario_a_quien_se_inscribe_despues(client, h_admin):
    alumno_inscrito(client, h_admin)
    rifa = crear_rifa(client, h_admin).json()
    nueva = alumno_inscrito(client, h_admin, documento="2000000003")
    r = client.post(f"{R}/{rifa['id']}/talonarios", headers=h_admin)
    assert r.json() == {"asignados": 1}
    assert nueva["id"] in {t["alumno_id"] for t in _talonarios(client, h_admin, rifa["id"])}
    assert client.post(f"{R}/{rifa['id']}/talonarios", headers=h_admin).json() == {"asignados": 0}


def test_maximo_de_rifas_por_anio_y_las_canceladas_no_cuentan(client, h_admin):
    for n in range(4):
        assert crear_rifa(client, h_admin, nombre=f"Rifa {n}").status_code == 201
    r = crear_rifa(client, h_admin, nombre="Rifa 5")
    assert r.status_code == 422 and "máximo" in r.json()["detail"]
    primera = client.get(R, headers=h_admin).json()[0]
    assert client.post(f"{R}/{primera['id']}/cancelar", json={}, headers=h_admin).status_code == 200  # sin motivo
    assert crear_rifa(client, h_admin, nombre="Rifa 5").json()["numero"] == 5


def test_rifa_con_fecha_pasada_o_de_otro_anio_se_rechaza(client, h_admin):
    assert crear_rifa(client, h_admin, fecha=LUNES - timedelta(days=1)).status_code == 422
    assert crear_rifa(client, h_admin, anio=2027).status_code == 422


def test_entrenador_y_miembro_no_crean_rifas_ni_registran_pagos(client, h_admin, crear_usuario, auth_header):
    alumno_inscrito(client, h_admin)
    rifa = crear_rifa(client, h_admin).json()
    t = _talonarios(client, h_admin, rifa["id"])[0]
    crear_usuario("coach@club.com", "ENTRENADOR", rama="femenina")
    crear_usuario("m@club.com", "MIEMBRO")
    for h in (auth_header("coach@club.com"), auth_header("m@club.com")):
        assert crear_rifa(client, h).status_code == 403
        assert _pagar_talonario(client, h, rifa["id"], t["id"], 2000).status_code == 403
        assert client.post(f"{R}/{rifa['id']}/sorteo", headers=h).status_code == 403
        assert client.delete(f"{R}/{rifa['id']}", headers=h).status_code == 403


# ---------- Pagos del talonario ----------
def test_pago_completo_o_por_abonos_del_talonario(client, h_admin):
    alumno_inscrito(client, h_admin)
    rifa = crear_rifa(client, h_admin).json()
    t = _talonarios(client, h_admin, rifa["id"])[0]
    t = _pagar_talonario(client, h_admin, rifa["id"], t["id"], 25000).json()
    assert (t["recaudado"], t["saldo"], t["pagado"]) == (25000, 15000, False)
    assert _pagar_talonario(client, h_admin, rifa["id"], t["id"], 20000).status_code == 422  # supera el saldo
    assert _pagar_talonario(client, h_admin, rifa["id"], t["id"], 1, fecha=LUNES + timedelta(days=1)).status_code == 422
    t = _pagar_talonario(client, h_admin, rifa["id"], t["id"], 15000).json()
    assert t["pagado"] is True and t["saldo"] == 0 and [p["monto"] for p in t["pagos"]] == [25000, 15000]
    assert "comprador_nombre" not in str(t)  # el talonario es del alumno: no hay compradores


def test_anular_un_pago_de_rifa_es_solo_del_superadmin_y_no_exige_motivo(client, h_admin, h_root):
    alumno_inscrito(client, h_admin)
    rifa = crear_rifa(client, h_admin).json()
    t = _talonarios(client, h_admin, rifa["id"])[0]
    pago = _pagar_talonario(client, h_admin, rifa["id"], t["id"], 40000).json()["pagos"][0]
    url = f"{R}/{rifa['id']}/talonarios/{t['id']}/pagos/{pago['id']}/anular"
    assert client.post(url, json={}, headers=h_admin).status_code == 403
    t = client.post(url, json={"motivo": "   "}, headers=h_root).json()
    assert (t["recaudado"], t["pagado"]) == (0, False)
    assert [(p["monto"], p["motivo"]) for p in t["pagos"]] == [(40000, None), (-40000, None)]
    assert client.post(url, json={}, headers=h_root).status_code == 409


def test_los_pagos_de_rifa_no_se_editan_ni_se_borran(client, h_admin, db):
    alumno_inscrito(client, h_admin)
    rifa = crear_rifa(client, h_admin).json()
    t = _talonarios(client, h_admin, rifa["id"])[0]
    _pagar_talonario(client, h_admin, rifa["id"], t["id"], 2000)
    for sentencia in ("UPDATE pagos_talonario SET monto = 1", "DELETE FROM pagos_talonario"):
        with pytest.raises(DBAPIError, match="solo agregar"):
            db.execute(text(sentencia))
        db.rollback()


# ---------- Sorteo ----------
def test_sorteo_solo_entre_talonarios_pagados_varias_jugadas_y_actas_inmutables(client, h_admin, reloj, db):
    pagada = alumno_inscrito(client, h_admin)
    alumno_inscrito(client, h_admin, documento="2000000003")
    rifa = crear_rifa(client, h_admin).json()
    talonarios = {t["alumno_id"]: t for t in _talonarios(client, h_admin, rifa["id"])}
    t = talonarios[pagada["id"]]
    _pagar_talonario(client, h_admin, rifa["id"], t["id"], 40000)
    otro = next(x for x in talonarios.values() if x["id"] != t["id"])
    _pagar_talonario(client, h_admin, rifa["id"], otro["id"], 38000)  # le falta: no participa

    r = client.post(f"{R}/{rifa['id']}/sorteo", headers=h_admin)
    assert r.status_code == 422 and "aún no" in r.json()["detail"]  # antes de la fecha

    reloj(en_hora(SORTEO, 20))
    boletas = [f"{t['codigo']}-{n:02d}" for n in range(1, 21)]
    ganadoras = set()
    for orden in (1, 2, 3):  # se puede jugar varias veces
        r = client.post(f"{R}/{rifa['id']}/sorteo", headers=h_admin)
        assert r.status_code == 201, r.text
        acta = r.json()
        en_urna = [b for b in boletas if b not in ganadoras]
        assert acta["orden"] == orden and acta["participantes"] == en_urna
        assert acta["total_participantes"] == 21 - orden and acta["huella"] == huella(en_urna)
        assert acta["alumno_id"] == pagada["id"] and acta["codigo"] == t["codigo"] == pagada["codigo"]
        ganadora = f"{acta['codigo']}-{acta['boleta']:02d}"
        assert ganadora in en_urna  # una boleta no gana dos veces
        ganadoras.add(ganadora)
    actas = client.get(f"{R}/{rifa['id']}/actas", headers=h_admin).json()
    assert [a["orden"] for a in actas] == [1, 2, 3]
    assert client.get(f"{R}/{rifa['id']}", headers=h_admin).json()["estado"] == "sorteada"

    with pytest.raises(DBAPIError, match="solo agregar"):
        db.execute(text("UPDATE actas_sorteo SET boleta = 0"))
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
    t = _talonarios(client, h_admin, rifa["id"])[0]
    client.post(f"{R}/{rifa['id']}/cancelar", json={"motivo": "Lluvia de deudas"}, headers=h_admin)
    assert _pagar_talonario(client, h_admin, rifa["id"], t["id"], 2000).status_code == 422
    reloj(en_hora(SORTEO, 20))
    assert client.post(f"{R}/{rifa['id']}/sorteo", headers=h_admin).status_code == 409


# ---------- Eliminar ----------
def test_eliminar_una_rifa_la_quita_de_todo_pero_conserva_la_evidencia(client, h_admin, h_root, db):
    alumna = alumno_inscrito(client, h_admin)
    vacia = crear_rifa(client, h_admin, nombre="Rifa de prueba").json()
    con_pagos = crear_rifa(client, h_admin, nombre="Rifa con plata").json()
    t = _talonarios(client, h_admin, con_pagos["id"])[0]
    _pagar_talonario(client, h_admin, con_pagos["id"], t["id"], 10000)

    # Sin dinero ni sorteos la elimina el Admin; con pagos, solo el SuperAdmin.
    assert client.delete(f"{R}/{vacia['id']}", headers=h_admin).status_code == 204
    assert client.delete(f"{R}/{con_pagos['id']}", headers=h_admin).status_code == 403
    assert client.delete(f"{R}/{con_pagos['id']}", headers=h_root).status_code == 204

    assert client.get(R, headers=h_admin).json() == []
    assert client.get(f"{R}/{vacia['id']}", headers=h_admin).status_code == 404
    e = client.get(f"{A}/{alumna['id']}/estado-cuenta", headers=h_admin).json()
    assert e["rifas"] == []  # ya no es deuda
    # Su número queda libre y no cuenta para el máximo del año.
    assert crear_rifa(client, h_admin, nombre="Rifa nueva").json()["numero"] == 1
    # El dinero que ya entró no se borra: queda como evidencia (y en la auditoría).
    assert db.scalar(text("SELECT count(*) FROM pagos_talonario")) == 1
    assert db.scalar(text("SELECT count(*) FROM auditoria WHERE accion = 'rifa.eliminar'")) == 2


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
