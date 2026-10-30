from datetime import timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.core.fechas import hoy
from app.models.sistema import Auditoria
from tests.fabrica import I, crear_acudiente, crear_alumno, crear_menor, datos_alumno, inscribir


@pytest.fixture
def h_admin(crear_usuario, auth_header):
    crear_usuario("adm@club.com", "ADMIN")
    return auth_header("adm@club.com")


@pytest.fixture
def h_root(crear_usuario, auth_header):
    crear_usuario("root@club.com", "SUPERADMIN")
    return auth_header("root@club.com")


@pytest.fixture
def alumno(client, h_admin):
    return crear_alumno(client, h_admin)


def _pagar(client, h, inscripcion_id, fecha=None, monto=90000):
    return client.post(
        f"{I}/{inscripcion_id}/pagos", json={"fecha_pago": (fecha or hoy()).isoformat(), "monto": monto}, headers=h
    )


def _prorrogar(client, h, inscripcion_id, dias=5, motivo="Acuerdo de pago con la familia"):
    cuerpo = {"nueva_fecha_limite": (hoy() + timedelta(days=dias)).isoformat(), "motivo": motivo}
    return client.post(f"{I}/{inscripcion_id}/prorroga", json=cuerpo, headers=h)


def _estado(client, h, inscripcion_id, estado, motivo="Motivo de prueba"):
    return client.post(f"{I}/{inscripcion_id}/estado", json={"estado": estado, "motivo": motivo}, headers=h)


# ---------- Creación ----------
def test_inscripcion_usa_plazo_y_valor_por_defecto(client, h_admin, alumno):
    r = inscribir(client, h_admin, alumno["id"])
    assert r.status_code == 201, r.text
    i = r.json()
    assert i["estado"] == "pendiente_pago" and i["valor"] == 90000 and i["rama"] == "femenina"
    assert i["fecha_limite_pago"] == (hoy() + timedelta(days=30)).isoformat()


def test_plazo_y_valor_se_leen_de_configuracion(client, h_admin, h_root, alumno):
    client.patch("/api/v1/configuracion/plazo_pago_dias", json={"valor": 10}, headers=h_root)
    client.patch("/api/v1/configuracion/valor_inscripcion", json={"valor": 100000}, headers=h_root)
    i = inscribir(client, h_admin, alumno["id"]).json()
    assert i["valor"] == 100000 and i["fecha_limite_pago"] == (hoy() + timedelta(days=10)).isoformat()


def test_solo_una_inscripcion_vigente_por_anio(client, h_admin, alumno):
    assert inscribir(client, h_admin, alumno["id"]).status_code == 201
    r = inscribir(client, h_admin, alumno["id"])
    assert r.status_code == 409 and "vigente" in r.json()["detail"]


def test_fecha_de_inscripcion_futura_se_rechaza(client, h_admin, alumno):
    assert inscribir(client, h_admin, alumno["id"], hoy() + timedelta(days=1)).status_code == 422


def test_mayor_sin_acudiente_se_inscribe_y_menor_sin_acudiente_no(client, h_admin, h_root, alumno):
    assert inscribir(client, h_admin, alumno["id"]).status_code == 201
    otro = crear_alumno(client, h_admin, documento="8888888888", anios=20)
    # El SuperAdmin sube la mayoría de edad: ese alumno de 20 años pasa a ser "menor" y no tiene acudiente.
    client.patch("/api/v1/configuracion/edad_mayoria", json={"valor": 21}, headers=h_root)
    r = inscribir(client, h_admin, otro["id"])
    assert r.status_code == 422 and "acudiente" in r.json()["detail"]


def test_menor_con_acudiente_se_inscribe(client, h_admin):
    assert inscribir(client, h_admin, crear_menor(client, h_admin)["id"]).status_code == 201


def test_miembro_no_se_inscribe_por_su_cuenta_pero_ve_la_inscripcion(client, h_admin, crear_usuario, auth_header):
    padre = crear_usuario("padre@club.com", "MIEMBRO")
    hijo = crear_menor(client, h_admin, acudiente=crear_acudiente(client, h_admin, usuario_id=str(padre.id)))
    h = auth_header("padre@club.com")
    assert inscribir(client, h, hijo["id"]).status_code == 403
    inscribir(client, h_admin, hijo["id"])
    i = client.get(I, headers=h).json()[0]
    assert i["alumno_id"] == hijo["id"]
    assert _pagar(client, h, i["id"]).status_code == 403
    assert _prorrogar(client, h, i["id"]).status_code == 403


def test_entrenador_inscribe_solo_su_rama_y_con_fecha_de_hoy(client, h_admin, alumno, crear_usuario, auth_header):
    crear_usuario("coach@club.com", "ENTRENADOR", rama="femenina")
    h = auth_header("coach@club.com")
    ajeno = crear_alumno(client, h_admin, documento="2222222222", rama="masculina")
    assert inscribir(client, h, ajeno["id"]).status_code == 404
    assert inscribir(client, h, alumno["id"], hoy() - timedelta(days=3)).status_code == 403
    r = inscribir(client, h, alumno["id"])
    assert r.status_code == 201
    # Registra abonos de su rama, pero las prórrogas siguen en manos de Admin/SuperAdmin.
    assert _pagar(client, h, r.json()["id"], monto=40000).json()["saldo"] == 50000
    assert _prorrogar(client, h, r.json()["id"], dias=40).status_code == 403


def test_entrenador_no_registra_abonos_de_otra_rama(client, h_admin, crear_usuario, auth_header):
    ajeno = crear_alumno(client, h_admin, documento="2222222222", rama="masculina")
    i = inscribir(client, h_admin, ajeno["id"]).json()
    crear_usuario("coach@club.com", "ENTRENADOR", rama="femenina")
    assert _pagar(client, auth_header("coach@club.com"), i["id"]).status_code == 404


def _anular(client, h, inscripcion_id, pago_id, motivo="Abono registrado dos veces por error"):
    return client.post(f"{I}/{inscripcion_id}/pagos/{pago_id}/anular", json={"motivo": motivo}, headers=h)


def test_superadmin_anula_un_abono_y_la_inscripcion_vuelve_a_pendiente(client, h_admin, h_root, alumno, db):
    i = inscribir(client, h_admin, alumno["id"]).json()
    _pagar(client, h_admin, i["id"], monto=40000)
    pagada = _pagar(client, h_admin, i["id"], monto=50000).json()
    assert pagada["estado"] == "activo"
    abono = pagada["pagos"][1]

    r = _anular(client, h_root, i["id"], abono["id"])
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["estado"] == "pendiente_pago" and cuerpo["saldo"] == 50000 and cuerpo["fecha_pago"] is None
    assert [(p["monto"], p["anulado"]) for p in cuerpo["pagos"]] == [(40000, False), (50000, True), (-50000, False)]
    assert cuerpo["pagos"][2]["anula_id"] == abono["id"]
    fila = db.scalar(select(Auditoria).where(Auditoria.accion == "inscripcion.anular_pago"))
    assert fila.despues["motivo"] == "Abono registrado dos veces por error"

    # Se puede volver a registrar el abono correcto.
    assert _pagar(client, h_admin, i["id"], monto=50000).json()["estado"] == "activo"


def test_anulacion_exige_superadmin_no_exige_motivo_y_no_se_repite(
    client, h_admin, h_root, alumno, crear_usuario, auth_header
):
    i = inscribir(client, h_admin, alumno["id"]).json()
    abono = _pagar(client, h_admin, i["id"], monto=40000).json()["pagos"][0]
    crear_usuario("coach@club.com", "ENTRENADOR", rama="femenina")
    assert _anular(client, h_admin, i["id"], abono["id"]).status_code == 403
    assert _anular(client, auth_header("coach@club.com"), i["id"], abono["id"]).status_code == 403

    anulacion = _anular(client, h_root, i["id"], abono["id"], motivo=None).json()["pagos"][1]
    assert anulacion["monto"] == -40000 and anulacion["motivo"] is None  # el motivo es opcional
    assert _anular(client, h_root, i["id"], abono["id"]).status_code == 409  # ya anulado
    assert _anular(client, h_root, i["id"], anulacion["id"]).status_code == 422  # no se anula una anulación


# ---------- Regla del plazo de pago ----------
def test_pago_dentro_del_plazo_activa_la_inscripcion(client, h_admin, alumno):
    i = inscribir(client, h_admin, alumno["id"], hoy() - timedelta(days=30)).json()  # último día del plazo
    r = _pagar(client, h_admin, i["id"])
    assert r.status_code == 200 and r.json()["estado"] == "activo" and r.json()["monto_pagado"] == 90000


def test_pago_fuera_del_plazo_se_rechaza_con_mensaje_claro(client, h_admin, alumno):
    i = inscribir(client, h_admin, alumno["id"], hoy() - timedelta(days=31)).json()
    r = _pagar(client, h_admin, i["id"])
    assert r.status_code == 422
    detalle = r.json()["detail"]
    assert "supera el plazo de 30 días" in detalle and "prórroga" in detalle
    assert client.get(f"{I}/{i['id']}", headers=h_admin).json()["estado"] == "pendiente_pago"


def test_abonos_parciales_hasta_completar_el_valor(client, h_admin, alumno, db):
    i = inscribir(client, h_admin, alumno["id"], hoy() - timedelta(days=10)).json()
    r = _pagar(client, h_admin, i["id"], hoy() - timedelta(days=5), monto=40000)
    assert r.status_code == 200
    assert r.json()["estado"] == "pendiente_pago" and r.json()["saldo"] == 50000 and r.json()["fecha_pago"] is None

    r = _pagar(client, h_admin, i["id"], monto=50000)
    cuerpo = r.json()
    assert cuerpo["estado"] == "activo" and cuerpo["saldo"] == 0 and cuerpo["monto_pagado"] == 90000
    assert cuerpo["fecha_pago"] == hoy().isoformat()
    assert [p["monto"] for p in cuerpo["pagos"]] == [40000, 50000]
    assert len(db.scalars(select(Auditoria).where(Auditoria.accion == "inscripcion.pago")).all()) == 2

    assert _pagar(client, h_admin, i["id"], monto=1000).status_code == 409  # ya está paga


def test_abono_mayor_al_saldo_se_rechaza(client, h_admin, alumno):
    i = inscribir(client, h_admin, alumno["id"]).json()
    _pagar(client, h_admin, i["id"], monto=40000)
    r = _pagar(client, h_admin, i["id"], monto=60000)
    assert r.status_code == 422 and "saldo pendiente ($50.000)" in r.json()["detail"]


def test_abono_fuera_del_plazo_se_rechaza_y_el_saldo_se_completa_con_prorroga(client, h_admin, alumno):
    i = inscribir(client, h_admin, alumno["id"], hoy() - timedelta(days=40)).json()
    assert _pagar(client, h_admin, i["id"], hoy() - timedelta(days=35), monto=30000).status_code == 200
    r = _pagar(client, h_admin, i["id"], monto=60000)
    assert r.status_code == 422 and "supera el plazo" in r.json()["detail"]

    assert client.post(f"{I}/vencer", headers=h_admin).json() == {"vencidas": 1}
    _prorrogar(client, h_admin, i["id"])
    r = _pagar(client, h_admin, i["id"], monto=60000)
    assert r.json()["estado"] == "activo" and [p["monto"] for p in r.json()["pagos"]] == [30000, 60000]


def test_los_abonos_no_se_pueden_editar_ni_borrar(client, h_admin, alumno, db):
    _pagar(client, h_admin, inscribir(client, h_admin, alumno["id"]).json()["id"], monto=10000)
    for sentencia in ("UPDATE pagos_inscripcion SET monto = 1", "DELETE FROM pagos_inscripcion"):
        with pytest.raises(DBAPIError, match="solo agregar"):
            db.execute(text(sentencia))
        db.rollback()


def test_inscripcion_gratis_queda_activa_de_una(client, h_admin, h_root, alumno):
    client.patch("/api/v1/configuracion/valor_inscripcion", json={"valor": 0}, headers=h_root)
    i = inscribir(client, h_admin, alumno["id"]).json()
    assert i["estado"] == "activo" and i["saldo"] == 0


def test_pago_con_fecha_futura_o_anterior_a_la_inscripcion_se_rechaza(client, h_admin, alumno):
    i = inscribir(client, h_admin, alumno["id"], hoy() - timedelta(days=5)).json()
    assert _pagar(client, h_admin, i["id"], hoy() + timedelta(days=1)).status_code == 422
    assert _pagar(client, h_admin, i["id"], hoy() - timedelta(days=6)).status_code == 422


# ---------- Prórrogas ----------
def test_prorroga_permite_pagar_fuera_del_plazo_original(client, h_admin, alumno, db):
    i = inscribir(client, h_admin, alumno["id"], hoy() - timedelta(days=40)).json()
    assert _pagar(client, h_admin, i["id"]).status_code == 422
    r = _prorrogar(client, h_admin, i["id"])
    assert r.status_code == 200
    assert r.json()["prorrogas"][0]["motivo"] == "Acuerdo de pago con la familia"
    assert _pagar(client, h_admin, i["id"]).status_code == 200
    acciones = {a.accion for a in db.scalars(select(Auditoria))}
    assert {"inscripcion.prorroga", "inscripcion.pago"} <= acciones


def test_prorroga_exige_motivo_fecha_posterior_y_permiso(client, h_admin, alumno, crear_usuario, auth_header):
    i = inscribir(client, h_admin, alumno["id"]).json()
    assert _prorrogar(client, h_admin, i["id"], motivo="corto").status_code == 422
    assert _prorrogar(client, h_admin, i["id"], dias=10).status_code == 422  # anterior al límite actual (30 días)
    crear_usuario("coach@club.com", "ENTRENADOR", rama="femenina")
    assert _prorrogar(client, auth_header("coach@club.com"), i["id"], dias=40).status_code == 403
    assert _prorrogar(client, h_admin, i["id"], dias=40).status_code == 200


def test_prorroga_no_se_puede_editar_ni_borrar(client, h_admin, alumno, db):
    i = inscribir(client, h_admin, alumno["id"]).json()
    _prorrogar(client, h_admin, i["id"], dias=40)
    for sentencia in ("UPDATE prorrogas SET motivo = 'cambiado'", "DELETE FROM prorrogas"):
        with pytest.raises(DBAPIError, match="solo agregar"):
            db.execute(text(sentencia))
        db.rollback()


def test_vencimiento_rechaza_y_la_prorroga_reactiva(client, h_admin, alumno, db):
    vencida = inscribir(client, h_admin, alumno["id"], hoy() - timedelta(days=40)).json()
    r = client.post(f"{I}/vencer", headers=h_admin)
    assert r.status_code == 200 and r.json() == {"vencidas": 1}
    i = client.get(f"{I}/{vencida['id']}", headers=h_admin).json()
    assert i["estado"] == "rechazado" and i["causa_rechazo"] == "vencimiento"

    r = _pagar(client, h_admin, vencida["id"])
    assert r.status_code == 422 and "prórroga" in r.json()["detail"]

    r = _prorrogar(client, h_admin, vencida["id"])
    assert r.status_code == 200 and r.json()["estado"] == "pendiente_pago" and r.json()["causa_rechazo"] is None
    assert _pagar(client, h_admin, vencida["id"]).json()["estado"] == "activo"
    assert "inscripcion.vencer" in {a.accion for a in db.scalars(select(Auditoria))}


def test_inscripcion_rechazada_a_mano_no_se_prorroga(client, h_admin, alumno):
    i = inscribir(client, h_admin, alumno["id"]).json()
    assert _estado(client, h_admin, i["id"], "rechazado").status_code == 200
    r = _prorrogar(client, h_admin, i["id"], dias=40)
    assert r.status_code == 422 and "vencimiento" in r.json()["detail"]


# ---------- Estados ----------
def test_ciclo_de_estados_y_quien_confirma_la_expulsion(client, h_admin, h_root, alumno, db):
    i = inscribir(client, h_admin, alumno["id"]).json()
    # pendiente -> activo solo se logra pagando
    r = _estado(client, h_admin, i["id"], "activo")
    assert r.status_code == 422 and "pago" in r.json()["detail"]
    _pagar(client, h_admin, i["id"])

    assert _estado(client, h_admin, i["id"], "a_expulsar").json()["estado"] == "a_expulsar"
    assert _estado(client, h_admin, i["id"], "activo").json()["estado"] == "activo"  # se puso al día
    _estado(client, h_admin, i["id"], "a_expulsar")

    r = _estado(client, h_admin, i["id"], "expulsado")  # el Admin no confirma expulsiones
    assert r.status_code == 403 and "SuperAdmin" in r.json()["detail"]
    assert _estado(client, h_root, i["id"], "expulsado").json()["estado"] == "expulsado"

    assert _estado(client, h_root, i["id"], "activo").status_code == 422  # expulsado es final
    cambios = db.scalars(select(Auditoria).where(Auditoria.accion == "inscripcion.estado")).all()
    assert len(cambios) == 4


def test_cambio_de_estado_exige_motivo(client, h_admin, alumno):
    i = inscribir(client, h_admin, alumno["id"]).json()
    r = client.post(f"{I}/{i['id']}/estado", json={"estado": "rechazado"}, headers=h_admin)
    assert r.status_code == 422 and "motivo" in r.json()["detail"]


def test_estado_invalido_se_rechaza_en_la_base(client, h_admin, alumno, db):
    i = inscribir(client, h_admin, alumno["id"]).json()
    with pytest.raises(DBAPIError):
        db.execute(text("UPDATE inscripciones SET estado = 'suspendido' WHERE id = :id"), {"id": i["id"]})
    db.rollback()


def test_entrenador_ve_inscripciones_de_su_rama(client, h_admin, alumno, crear_usuario, auth_header):
    otra = crear_alumno(client, h_admin, documento="2222222222", rama="masculina")
    inscribir(client, h_admin, alumno["id"])
    inscribir(client, h_admin, otra["id"])
    crear_usuario("coach@club.com", "ENTRENADOR", rama="masculina")
    filas = client.get(I, headers=auth_header("coach@club.com")).json()
    assert [f["alumno_id"] for f in filas] == [otra["id"]]


# ---------- Alta de alumno nuevo: ficha + inscripción + primer pago, todo o nada ----------
NUEVO = f"{I}/alumno-nuevo"


def _cuantos_alumnos(db) -> int:
    return db.scalar(text("SELECT count(*) FROM alumnos"))


def test_alta_de_alumno_nuevo_lo_inscribe_y_registra_el_abono(client, h_admin):
    cuerpo = {"alumno": datos_alumno(), "pago": {"forma": "parcial", "monto": 40000}}
    r = client.post(NUEVO, json=cuerpo, headers=h_admin)
    assert r.status_code == 201, r.text
    i = r.json()
    assert (i["estado"], i["monto_pagado"], i["saldo"], i["anio"]) == ("pendiente_pago", 40000, 50000, hoy().year)
    assert i["alumno_nombre"] == "Laura Pérez" and len(i["pagos"]) == 1

    completo = client.post(NUEVO, json={"alumno": datos_alumno(documento="2222222222"), "pago": {"forma": "completo"}},
                           headers=h_admin).json()
    assert (completo["estado"], completo["saldo"]) == ("activo", 0)
    sin_pago = client.post(NUEVO, json={"alumno": datos_alumno(documento="3333333333")}, headers=h_admin).json()
    assert (sin_pago["estado"], sin_pago["monto_pagado"]) == ("pendiente_pago", None)


@pytest.mark.parametrize("cuerpo, error", [
    ({"alumno": datos_alumno(), "pago": {"forma": "parcial", "monto": 999999}}, "supera"),  # abono > valor
    ({"alumno": datos_alumno(anios=12)}, "menor de edad"),  # menor sin acudiente
])
def test_alta_que_falla_no_deja_nada_a_medias(client, h_admin, db, cuerpo, error):
    r = client.post(NUEVO, json=cuerpo, headers=h_admin)
    assert r.status_code == 422 and error in r.text
    assert _cuantos_alumnos(db) == 0  # ni el alumno quedó creado


def test_alta_parcial_sin_monto_y_documento_repetido(client, h_admin, db):
    assert client.post(NUEVO, json={"alumno": datos_alumno(), "pago": {"forma": "parcial"}},
                       headers=h_admin).status_code == 422
    crear_alumno(client, h_admin)
    assert client.post(NUEVO, json={"alumno": datos_alumno()}, headers=h_admin).status_code == 409
    assert _cuantos_alumnos(db) == 1


def test_alta_de_alumno_nuevo_permisos(client, h_admin, crear_usuario, auth_header, db):
    crear_usuario("coach@club.com", "ENTRENADOR", rama="femenina")
    h_coach = auth_header("coach@club.com")
    crear_usuario("familia@club.com", "MIEMBRO")
    h_familia = auth_header("familia@club.com")

    assert client.post(NUEVO, json={"alumno": datos_alumno()}, headers=h_familia).status_code == 403
    # El entrenador asistente solo inscribe en su rama…
    otra = {"alumno": datos_alumno(rama="masculina"), "pago": {"forma": "completo"}}
    assert client.post(NUEVO, json=otra, headers=h_coach).status_code == 403
    assert _cuantos_alumnos(db) == 0
    # …y en la suya sí, con el pago incluido.
    r = client.post(NUEVO, json={"alumno": datos_alumno(), "pago": {"forma": "completo"}}, headers=h_coach)
    assert r.status_code == 201 and r.json()["estado"] == "activo"
