from datetime import timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from tests.fabrica import INICIO, LUNES, T, ajustar_permisos, crear_torneo, en_hora, inscribir_equipo


def _pagar(client, h, torneo_id, equipo_id, monto, fecha=LUNES):
    return client.post(f"{T}/{torneo_id}/equipos/{equipo_id}/pagos",
                       json={"monto": monto, "fecha": fecha.isoformat()}, headers=h)


# ---------- Torneos ----------
def test_crear_torneo_toma_el_cupo_sugerido_de_configuracion(client, h_admin):
    r = crear_torneo(client, h_admin)
    assert r.status_code == 201, r.text
    assert r.json()["cupo_equipos"] == 18 and r.json()["valor_inscripcion"] == 150000
    assert crear_torneo(client, h_admin, nombre="Copa chica", cupo_equipos=8).json()["cupo_equipos"] == 8


def test_fechas_del_torneo_se_validan(client, h_admin):
    assert crear_torneo(client, h_admin, fecha_inicio=(LUNES - timedelta(days=1)).isoformat()).status_code == 422
    assert crear_torneo(client, h_admin, fecha_fin=(INICIO - timedelta(days=1)).isoformat()).status_code == 422
    tarde = (INICIO + timedelta(days=1)).isoformat()
    assert crear_torneo(client, h_admin, fecha_limite_inscripcion=tarde).status_code == 422


def test_solo_el_staff_maneja_torneos(client, h_admin, crear_usuario, auth_header):
    torneo = crear_torneo(client, h_admin).json()
    crear_usuario("coach@club.com", "ENTRENADOR")
    crear_usuario("m@club.com", "MIEMBRO")
    for h in (auth_header("coach@club.com"), auth_header("m@club.com")):
        assert crear_torneo(client, h).status_code == 403
        assert client.get(f"{T}/{torneo['id']}/equipos", headers=h).status_code == 403  # datos de delegados
        assert inscribir_equipo(client, h, torneo["id"]).status_code == 403


# ---------- Inscripción de clubes ----------
def test_cupo_lleno_manda_a_lista_de_espera(client, h_admin):
    torneo = crear_torneo(client, h_admin, cupo_equipos=2).json()
    estados = [inscribir_equipo(client, h_admin, torneo["id"], club=f"Club {n}").json()["estado"] for n in range(3)]
    assert estados == ["pendiente_pago", "pendiente_pago", "en_espera"]
    resumen = client.get(f"{T}/{torneo['id']}", headers=h_admin).json()
    assert (resumen["ocupados"], resumen["en_espera"]) == (2, 1)


def test_un_club_no_se_inscribe_dos_veces(client, h_admin):
    torneo = crear_torneo(client, h_admin).json()
    assert inscribir_equipo(client, h_admin, torneo["id"], club="Club Halcones").status_code == 201
    r = inscribir_equipo(client, h_admin, torneo["id"], club="club HALCONES")
    assert r.status_code == 409 and "ya tiene equipo" in r.json()["detail"]


def test_despues_de_la_fecha_limite_no_entran_equipos(client, h_admin, reloj):
    torneo = crear_torneo(client, h_admin).json()
    reloj(en_hora(INICIO - timedelta(days=4), 9))
    r = inscribir_equipo(client, h_admin, torneo["id"])
    assert r.status_code == 422 and "cerraron" in r.json()["detail"]


def test_torneo_cancelado_no_recibe_equipos_ni_pagos(client, h_admin):
    torneo = crear_torneo(client, h_admin).json()
    equipo = inscribir_equipo(client, h_admin, torneo["id"]).json()
    client.post(f"{T}/{torneo['id']}/cancelar", json={"motivo": "Coliseo en obras"}, headers=h_admin)
    assert inscribir_equipo(client, h_admin, torneo["id"], club="Otro club").status_code == 422
    assert _pagar(client, h_admin, torneo["id"], equipo["id"], 1000).status_code == 422


def test_datos_del_delegado_se_validan(client, h_admin):
    torneo = crear_torneo(client, h_admin).json()
    assert inscribir_equipo(client, h_admin, torneo["id"], delegado_telefono="12").status_code == 422
    assert inscribir_equipo(client, h_admin, torneo["id"], delegado_email="no-es-correo").status_code == 422


# ---------- Pagos ----------
def test_abonos_confirman_al_equipo_al_completar_el_valor(client, h_admin):
    torneo = crear_torneo(client, h_admin).json()
    equipo = inscribir_equipo(client, h_admin, torneo["id"]).json()
    r = _pagar(client, h_admin, torneo["id"], equipo["id"], 100000)
    assert r.json()["estado"] == "pendiente_pago" and r.json()["saldo"] == 50000
    r = _pagar(client, h_admin, torneo["id"], equipo["id"], 60000)
    assert r.status_code == 422 and "$50.000" in r.json()["detail"]
    r = _pagar(client, h_admin, torneo["id"], equipo["id"], 50000)
    assert r.json()["estado"] == "confirmado" and r.json()["saldo"] == 0
    assert client.get(f"{T}/{torneo['id']}", headers=h_admin).json()["recaudado"] == 150000


def test_en_lista_de_espera_no_se_paga(client, h_admin):
    torneo = crear_torneo(client, h_admin, cupo_equipos=2).json()
    for n in range(2):
        inscribir_equipo(client, h_admin, torneo["id"], club=f"Club {n}")
    espera = inscribir_equipo(client, h_admin, torneo["id"], club="Club tarde").json()
    assert _pagar(client, h_admin, torneo["id"], espera["id"], 1000).status_code == 409


def test_torneo_gratis_confirma_de_una(client, h_admin):
    torneo = crear_torneo(client, h_admin, valor_inscripcion=0).json()
    assert inscribir_equipo(client, h_admin, torneo["id"]).json()["estado"] == "confirmado"


def test_anular_pago_de_equipo_exige_permiso_y_lo_devuelve_a_pendiente(client, h_admin, h_root, h_entrenador):
    torneo = crear_torneo(client, h_admin).json()
    equipo = inscribir_equipo(client, h_admin, torneo["id"]).json()
    pagado = _pagar(client, h_admin, torneo["id"], equipo["id"], 150000).json()
    url = f"{T}/{torneo['id']}/equipos/{equipo['id']}/pagos/{pagado['pagos'][0]['id']}/anular"
    cuerpo = {"motivo": "El club pagó a otro torneo"}
    assert client.post(url, json=cuerpo, headers=h_entrenador).status_code == 403  # sin pagos.anular
    r = client.post(url, json=cuerpo, headers=h_root)
    assert r.json()["estado"] == "pendiente_pago" and r.json()["saldo"] == 150000


def test_los_pagos_de_equipos_no_se_editan_ni_se_borran(client, h_admin, db):
    torneo = crear_torneo(client, h_admin).json()
    equipo = inscribir_equipo(client, h_admin, torneo["id"]).json()
    _pagar(client, h_admin, torneo["id"], equipo["id"], 1000)
    for sentencia in ("UPDATE pagos_equipo SET monto = 1", "DELETE FROM pagos_equipo"):
        with pytest.raises(DBAPIError, match="solo agregar"):
            db.execute(text(sentencia))
        db.rollback()


# ---------- Retiros y lista de espera ----------
def test_al_retirarse_un_equipo_entra_el_primero_en_espera(client, h_admin):
    torneo = crear_torneo(client, h_admin, cupo_equipos=2).json()
    primero = inscribir_equipo(client, h_admin, torneo["id"], club="Club A").json()
    inscribir_equipo(client, h_admin, torneo["id"], club="Club B")
    espera_1 = inscribir_equipo(client, h_admin, torneo["id"], club="Club C").json()
    inscribir_equipo(client, h_admin, torneo["id"], club="Club D")

    r = client.post(f"{T}/{torneo['id']}/equipos/{primero['id']}/retirar", json={"motivo": "Sin presupuesto"},
                    headers=h_admin)
    assert r.status_code == 200
    assert r.json()["retirado"]["estado"] == "retirado"
    assert r.json()["promovido"]["id"] == espera_1["id"] and r.json()["promovido"]["estado"] == "pendiente_pago"
    # El club retirado puede volver a inscribirse (queda de último en espera).
    assert inscribir_equipo(client, h_admin, torneo["id"], club="Club A").json()["estado"] == "en_espera"


def test_retirar_a_uno_en_espera_no_promueve_a_nadie(client, h_admin):
    torneo = crear_torneo(client, h_admin, cupo_equipos=2).json()
    for n in range(2):
        inscribir_equipo(client, h_admin, torneo["id"], club=f"Club {n}")
    espera = inscribir_equipo(client, h_admin, torneo["id"], club="Club tarde").json()
    r = client.post(f"{T}/{torneo['id']}/equipos/{espera['id']}/retirar", json={"motivo": "Ya no vienen"},
                    headers=h_admin)
    assert r.json()["promovido"] is None
    assert client.post(f"{T}/{torneo['id']}/equipos/{espera['id']}/retirar", json={"motivo": "Otra vez"},
                       headers=h_admin).status_code == 409


# ---------- Editar y eliminar ----------
def test_editar_torneo_valida_fechas_y_al_subir_el_cupo_entran_los_que_esperan(client, h_admin):
    torneo = crear_torneo(client, h_admin, cupo_equipos=2).json()
    for n in range(3):
        inscribir_equipo(client, h_admin, torneo["id"], club=f"Club {n}")
    url = f"{T}/{torneo['id']}"
    assert client.patch(url, json={"cupo_equipos": 1}, headers=h_admin).status_code == 422  # ya hay 2 con cupo
    assert client.patch(url, json={"fecha_fin": (INICIO - timedelta(days=1)).isoformat()},
                        headers=h_admin).status_code == 422
    r = client.patch(url, json={"cupo_equipos": 3, "lugar": "Coliseo Mayor", "valor_inscripcion": 0}, headers=h_admin)
    assert r.status_code == 200, r.text
    assert (r.json()["cupo_equipos"], r.json()["lugar"], r.json()["ocupados"], r.json()["en_espera"]) == (
        3, "Coliseo Mayor", 3, 0,
    )
    # El valor nuevo es para los que se inscriban después; el promovido conserva el suyo.
    equipos = client.get(f"{url}/equipos", headers=h_admin).json()
    estados = {e["nombre_club"]: (e["estado"], e["valor"]) for e in equipos}
    assert estados["Club 2"] == ("pendiente_pago", 150000)
    assert client.patch(url, json={"rama": "mixta"}, headers=h_admin).status_code == 422


def test_eliminar_torneo_lo_quita_y_con_pagos_exige_poder_anularlos(client, h_admin, h_root, db):
    from sqlalchemy import text

    vacio = crear_torneo(client, h_admin, nombre="Torneo de prueba").json()
    con_pago = crear_torneo(client, h_admin, nombre="Copa con plata").json()
    equipo = inscribir_equipo(client, h_admin, con_pago["id"]).json()
    _pagar(client, h_admin, con_pago["id"], equipo["id"], 50000)

    ajustar_permisos(client, h_root, h_admin, quitar={"pagos.anular"})  # con pagos hace falta poder anularlos
    assert client.delete(f"{T}/{vacio['id']}", headers=h_admin).status_code == 204
    assert client.delete(f"{T}/{con_pago['id']}", headers=h_admin).status_code == 403
    assert client.delete(f"{T}/{con_pago['id']}", headers=h_root).status_code == 204
    assert client.get(T, headers=h_admin).json() == []
    assert client.get(f"{T}/{vacio['id']}", headers=h_admin).status_code == 404
    assert db.scalar(text("SELECT count(*) FROM pagos_equipo")) == 1  # el dinero queda como evidencia


# ---------- Jornadas, rama del equipo y sedes ----------
SABADO, DOMINGO = INICIO, INICIO + timedelta(days=1)
SEDES = ["Coliseo Mayor", "Coliseo Barrio Sur"]


def torneo_fin_de_semana(client, h, **extra):
    """Sábado femenina y domingo masculina, cada día en dos coliseos; un solo cupo y valor para todo el torneo."""
    return crear_torneo(client, h, rama=None, cupo_equipos=3, jornadas=[
        {"rama": "femenina", "fecha": SABADO.isoformat(), "sedes": SEDES},
        {"rama": "masculina", "fecha": DOMINGO.isoformat(), "sedes": SEDES},
    ], **extra)


def test_torneo_con_dos_jornadas_y_sus_sedes(client, h_admin):
    r = torneo_fin_de_semana(client, h_admin)
    assert r.status_code == 201, r.text
    t = r.json()
    assert t["rama"] is None  # tiene las dos
    assert [(j["rama"], j["fecha"], j["sedes"]) for j in t["jornadas"]] == [
        ("femenina", SABADO.isoformat(), SEDES), ("masculina", DOMINGO.isoformat(), SEDES),
    ]
    # Una sola rama (en corto): una jornada el día de inicio, sin sedes.
    corto = crear_torneo(client, h_admin, nombre="Copa corta").json()
    assert corto["rama"] == "femenina" and corto["jornadas"] == [
        {"rama": "femenina", "fecha": INICIO.isoformat(), "sedes": []},
    ]


@pytest.mark.parametrize("cambio", [
    {"rama": "femenina", "jornadas": [{"rama": "femenina", "fecha": SABADO.isoformat()}]},  # las dos a la vez
    {"jornadas": []},
    {"jornadas": [{"rama": "femenina", "fecha": SABADO.isoformat(), "sedes": ["Coliseo", "coliseo"]}]},
    {"jornadas": [{"rama": "femenina", "fecha": SABADO.isoformat()}] * 2},
    {"jornadas": [{"rama": "mixta", "fecha": SABADO.isoformat()}]},
    {"jornadas": [{"rama": "femenina", "fecha": SABADO.isoformat(), "sedes": ["x" * 121]}]},
])
def test_jornadas_invalidas(client, h_admin, cambio):
    cuerpo = {"rama": None, **cambio}
    assert crear_torneo(client, h_admin, **cuerpo).status_code == 422


def test_las_jornadas_quedan_dentro_de_las_fechas_del_torneo(client, h_admin):
    r = crear_torneo(client, h_admin, rama=None, jornadas=[
        {"rama": "femenina", "fecha": (INICIO + timedelta(days=5)).isoformat()},
    ])
    assert r.status_code == 422 and "entre la fecha de inicio" in r.json()["detail"]


def test_cada_club_se_inscribe_por_rama_con_un_solo_cupo(client, h_admin):
    t = torneo_fin_de_semana(client, h_admin).json()
    r = inscribir_equipo(client, h_admin, t["id"])  # sin rama, y el torneo tiene las dos
    assert r.status_code == 422 and "Elige la rama" in r.json()["detail"]
    assert inscribir_equipo(client, h_admin, t["id"], rama="femenina").json()["rama"] == "femenina"
    # El mismo club puede llevar su equipo masculino, pero no dos femeninos.
    assert inscribir_equipo(client, h_admin, t["id"], rama="masculina").status_code == 201
    assert inscribir_equipo(client, h_admin, t["id"], club="club halcones", rama="femenina").status_code == 409
    # El cupo es uno para todo el torneo: el tercero entra y el cuarto espera.
    tercero = inscribir_equipo(client, h_admin, t["id"], club="Club Águilas", rama="masculina").json()
    cuarto = inscribir_equipo(client, h_admin, t["id"], club="Club Tigres", rama="femenina").json()
    assert (tercero["estado"], cuarto["estado"]) == ("pendiente_pago", "en_espera")
    # En un torneo de una sola rama no hace falta elegirla, y no se acepta la otra.
    corto = crear_torneo(client, h_admin, nombre="Copa corta").json()
    assert inscribir_equipo(client, h_admin, corto["id"]).json()["rama"] == "femenina"
    r = inscribir_equipo(client, h_admin, corto["id"], club="Otro", rama="masculina")
    assert r.status_code == 422 and "no tiene rama masculina" in r.json()["detail"]


def test_el_organizador_asigna_la_sede_de_cada_equipo(client, h_admin, h_entrenador):
    t = torneo_fin_de_semana(client, h_admin).json()
    e = inscribir_equipo(client, h_admin, t["id"], rama="femenina").json()
    assert e["sede"] is None
    url = f"{T}/{t['id']}/equipos/{e['id']}/sede"
    r = client.put(url, json={"sede": "Coliseo Barrio Sur"}, headers=h_admin)
    assert r.status_code == 200 and r.json()["sede"] == "Coliseo Barrio Sur"
    r = client.put(url, json={"sede": "Coliseo de otro lado"}, headers=h_admin)
    assert r.status_code == 422 and "no es una sede" in r.json()["detail"]
    assert client.put(url, json={"sede": "Coliseo Mayor", "otro": 1}, headers=h_admin).status_code == 422
    assert client.put(url, json={"sede": "Coliseo Mayor"}, headers=h_entrenador).status_code == 403
    assert client.put(url, json={"sede": None}, headers=h_admin).json()["sede"] is None
    # Un equipo retirado ya no recibe sede, ni un equipo de otro torneo (404).
    client.post(f"{T}/{t['id']}/equipos/{e['id']}/retirar", json={}, headers=h_admin)
    assert client.put(url, json={"sede": "Coliseo Mayor"}, headers=h_admin).status_code == 409
    otro = torneo_fin_de_semana(client, h_admin, nombre="Otra copa").json()
    ajeno = f"{T}/{otro['id']}/equipos/{e['id']}/sede"
    assert client.put(ajeno, json={"sede": None}, headers=h_admin).status_code == 404


def test_editar_jornadas_cuida_a_los_equipos(client, h_admin):
    t = torneo_fin_de_semana(client, h_admin).json()
    e = inscribir_equipo(client, h_admin, t["id"], rama="masculina").json()
    client.put(f"{T}/{t['id']}/equipos/{e['id']}/sede", json={"sede": "Coliseo Mayor"}, headers=h_admin)
    # Sin la jornada masculina no se puede: hay un equipo inscrito en esa rama.
    solo_sabado = [{"rama": "femenina", "fecha": SABADO.isoformat(), "sedes": SEDES}]
    r = client.patch(f"{T}/{t['id']}", json={"jornadas": solo_sabado}, headers=h_admin)
    assert r.status_code == 422 and "rama masculina" in r.json()["detail"]
    # Si su sede deja de estar en la jornada, el equipo queda sin sede asignada.
    r = client.patch(f"{T}/{t['id']}", json={"jornadas": [
        solo_sabado[0], {"rama": "masculina", "fecha": DOMINGO.isoformat(), "sedes": ["Coliseo Barrio Sur"]},
    ]}, headers=h_admin)
    assert r.status_code == 200, r.text
    [equipo] = client.get(f"{T}/{t['id']}/equipos", headers=h_admin).json()
    assert equipo["sede"] is None
    # Mover el inicio de un torneo de una sola jornada mueve también su jornada.
    corto = crear_torneo(client, h_admin, nombre="Copa corta").json()
    nuevo_inicio = INICIO + timedelta(days=1)
    r = client.patch(f"{T}/{corto['id']}", json={"fecha_inicio": nuevo_inicio.isoformat(),
                                                 "fecha_fin": nuevo_inicio.isoformat()}, headers=h_admin)
    assert r.status_code == 200 and r.json()["jornadas"][0]["fecha"] == nuevo_inicio.isoformat()
    # Cambiar la rama (en corto) la cambia en su jornada.
    r = client.patch(f"{T}/{corto['id']}", json={"rama": "masculina"}, headers=h_admin)
    assert r.json()["rama"] == "masculina" and r.json()["jornadas"][0]["rama"] == "masculina"
    assert client.patch(f"{T}/{corto['id']}", json={"rama": "femenina", "jornadas": solo_sabado},
                        headers=h_admin).status_code == 422

