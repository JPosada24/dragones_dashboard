import json
from datetime import timedelta

import pytest
from sqlalchemy import select, update

from app.models.asistencia import Sesion
from app.models.sistema import Auditoria
from tests.fabrica import (
    LUNES,
    J,
    M,
    S,
    alumno_inscrito,
    cerrar_dia,
    crear_alumno,
    crear_sesion,
    en_hora,
    justificar,
    marcar_asistencia,
    ver_planilla,
)


# ---------- Sesiones extra (las del horario las crea la programación automática) ----------
def test_sesion_extra_no_en_el_pasado_ni_con_horario_invalido_ni_duplicada(client, h_admin):
    assert client.post(S, json={"fecha": (LUNES - timedelta(days=1)).isoformat(),
                                "hora_inicio": "18:00", "hora_fin": "20:00"}, headers=h_admin).status_code == 422
    assert client.post(S, json={"fecha": LUNES.isoformat(),
                                "hora_inicio": "20:00", "hora_fin": "18:00"}, headers=h_admin).status_code == 422
    crear_sesion(client, h_admin)
    assert client.post(S, json={"fecha": LUNES.isoformat(), "hora_inicio": "18:00",
                                "hora_fin": "19:00"}, headers=h_admin).status_code == 409


def test_entrenador_y_miembro_ven_las_sesiones_pero_no_las_gestionan(client, h_admin, familia, crear_usuario,
                                                                    auth_header):
    sesion = crear_sesion(client, h_admin)
    crear_usuario("coach@club.com", "ENTRENADOR", rama="masculina")
    for h in (auth_header("coach@club.com"), familia["h"]):
        assert [s["id"] for s in client.get(S, headers=h).json()] == [sesion["id"]]  # el entrenamiento es general
        assert client.post(S, json={"fecha": LUNES.isoformat(), "hora_inicio": "08:00", "hora_fin": "09:00"},
                           headers=h).status_code == 403
        assert client.post(f"{S}/{sesion['id']}/cancelar", json={"motivo": "Otro evento"},
                           headers=h).status_code == 403


# ---------- Planilla y marcación del grupo ----------
def test_planilla_incluye_a_los_inscritos_vigentes_de_ambas_ramas(client, h_admin):
    inscrita = alumno_inscrito(client, h_admin)
    crear_alumno(client, h_admin, documento="2000000001")  # sin inscripción
    inscrito = alumno_inscrito(client, h_admin, documento="2000000002", rama="masculina")
    sesion = crear_sesion(client, h_admin)
    planilla = ver_planilla(client, h_admin, sesion["id"])
    assert set(planilla) == {inscrita["id"], inscrito["id"]}
    assert planilla[inscrito["id"]]["rama"] == "masculina"


def test_entrenador_ve_y_marca_solo_su_rama_en_la_sesion_general(client, h_admin, crear_usuario, auth_header):
    alumna = alumno_inscrito(client, h_admin)
    alumno = alumno_inscrito(client, h_admin, documento="2000000002", rama="masculina")
    sesion = crear_sesion(client, h_admin)
    crear_usuario("coach@club.com", "ENTRENADOR", rama="femenina")
    h = auth_header("coach@club.com")
    assert list(ver_planilla(client, h, sesion["id"])) == [alumna["id"]]
    assert marcar_asistencia(client, h, sesion["id"], (alumno["id"], "presente")).status_code == 422
    assert ver_planilla(client, h_admin, sesion["id"])[alumno["id"]]["asistencia"] is None


def test_entrenador_marca_su_grupo(client, h_admin, crear_usuario, auth_header):
    alumna = alumno_inscrito(client, h_admin)
    otra = alumno_inscrito(client, h_admin, documento="2000000003")
    sesion = crear_sesion(client, h_admin)
    crear_usuario("coach@club.com", "ENTRENADOR", rama="femenina")
    h = auth_header("coach@club.com")
    r = marcar_asistencia(client, h, sesion["id"], (alumna["id"], "presente"), (otra["id"], "ausente"))
    assert r.status_code == 200
    filas = {f["alumno_id"]: f["asistencia"] for f in r.json()}
    assert filas == {alumna["id"]: "presente", otra["id"]: "ausente"}


def test_no_se_marca_a_quien_no_es_de_la_sesion_ni_una_sesion_futura(client, h_admin):
    ajeno = crear_alumno(client, h_admin, documento="2000000002")  # sin inscripción
    hoy_ = crear_sesion(client, h_admin)
    assert marcar_asistencia(client, h_admin, hoy_["id"], (ajeno["id"], "presente")).status_code == 422
    alumna = alumno_inscrito(client, h_admin)
    futura = crear_sesion(client, h_admin, dia=LUNES + timedelta(days=2))
    assert marcar_asistencia(client, h_admin, futura["id"], (alumna["id"], "presente")).status_code == 422


# ---------- Cierre diario y multas ----------
def test_cierre_genera_ausencia_y_multa_solo_a_quien_no_marco_ni_justifico(client, h_admin, reloj, db):
    presente = alumno_inscrito(client, h_admin)
    falto = alumno_inscrito(client, h_admin, documento="2000000003")
    sesion = crear_sesion(client, h_admin)
    marcar_asistencia(client, h_admin, sesion["id"], (presente["id"], "presente"))

    reloj(en_hora(LUNES, 23, 0))  # antes de las 23:59 todavía no se cierra
    assert cerrar_dia(client, h_admin) == {"sesiones": 0, "ausencias": 0, "multas": 0}

    reloj(en_hora(LUNES, 23, 59))
    assert cerrar_dia(client, h_admin) == {"sesiones": 1, "ausencias": 1, "multas": 1}
    planilla = ver_planilla(client, h_admin, sesion["id"])
    assert planilla[presente["id"]]["multa"] is None
    assert planilla[falto["id"]]["asistencia"] == "ausente" and planilla[falto["id"]]["multa"] == "pendiente"
    multas = client.get(M, headers=h_admin).json()
    assert [(m["alumno_id"], m["valor"]) for m in multas] == [(falto["id"], 2000)]

    # Cerrar de nuevo no duplica nada.
    assert cerrar_dia(client, h_admin) == {"sesiones": 0, "ausencias": 0, "multas": 0}
    assert "sesion.cerrar" in {a.accion for a in db.scalars(select(Auditoria))}


def test_valor_de_la_multa_sale_de_configuracion_y_cero_las_desactiva(client, h_root, reloj):
    alumna = alumno_inscrito(client, h_root)
    s1 = crear_sesion(client, h_root)
    client.patch("/api/v1/configuracion/multa_inasistencia", json={"valor": 3000}, headers=h_root)
    reloj(en_hora(LUNES, 23, 59))
    cerrar_dia(client, h_root)
    assert client.get(M, headers=h_root).json()[0]["valor"] == 3000

    reloj(en_hora(LUNES + timedelta(days=1), 10))
    s2 = crear_sesion(client, h_root, dia=LUNES + timedelta(days=1))
    client.patch("/api/v1/configuracion/multa_inasistencia", json={"valor": 0}, headers=h_root)
    reloj(en_hora(LUNES + timedelta(days=1), 23, 59))
    assert cerrar_dia(client, h_root)["multas"] == 0
    assert ver_planilla(client, h_root, s2["id"])[alumna["id"]]["asistencia"] == "ausente"
    assert s1["id"] != s2["id"]


def test_marcar_despues_del_cierre_exige_correccion(client, h_admin, reloj):
    alumna = alumno_inscrito(client, h_admin)
    sesion = crear_sesion(client, h_admin)
    reloj(en_hora(LUNES, 23, 59))
    cerrar_dia(client, h_admin)
    r = marcar_asistencia(client, h_admin, sesion["id"], (alumna["id"], "presente"))
    assert r.status_code == 422 and "corrección" in r.json()["detail"]


# ---------- Marcación propia ----------
def test_miembro_marca_la_asistencia_de_su_hija_solo_en_el_horario(client, h_admin, familia, reloj):
    sesion = crear_sesion(client, h_admin)
    cuerpo = {"alumno_id": familia["hija"]["id"]}
    reloj(en_hora(LUNES, 17, 0))  # más de 30 min antes
    r = client.post(f"{S}/{sesion['id']}/asistencia/propia", json=cuerpo, headers=familia["h"])
    assert r.status_code == 422 and "17:30" in r.json()["detail"]
    reloj(en_hora(LUNES, 17, 45))
    assert client.post(f"{S}/{sesion['id']}/asistencia/propia", json=cuerpo, headers=familia["h"]).status_code == 204
    assert client.post(f"{S}/{sesion['id']}/asistencia/propia", json=cuerpo, headers=familia["h"]).status_code == 409


def test_miembro_no_marca_a_otro_alumno_ni_sobre_lo_que_marco_el_entrenador(client, h_admin, familia, reloj):
    ajena = alumno_inscrito(client, h_admin, documento="2000000009")
    sesion = crear_sesion(client, h_admin)
    reloj(en_hora(LUNES, 18, 30))
    r = client.post(f"{S}/{sesion['id']}/asistencia/propia", json={"alumno_id": ajena["id"]}, headers=familia["h"])
    assert r.status_code == 404
    marcar_asistencia(client, h_admin, sesion["id"], (familia["hija"]["id"], "ausente"))
    r = client.post(f"{S}/{sesion['id']}/asistencia/propia", json={"alumno_id": familia["hija"]["id"]},
                    headers=familia["h"])
    assert r.status_code == 409


def test_miembro_solo_ve_su_fila_en_la_planilla(client, h_admin, familia):
    alumno_inscrito(client, h_admin, documento="2000000009")
    sesion = crear_sesion(client, h_admin)
    assert list(ver_planilla(client, familia["h"], sesion["id"])) == [familia["hija"]["id"]]


# ---------- Justificaciones ----------
def test_justificacion_pendiente_evita_la_multa_y_si_se_aprueba_queda_justificado(client, h_admin, familia, reloj):
    sesion = crear_sesion(client, h_admin)
    j = justificar(client, familia["h"], sesion["id"], familia["hija"]["id"])
    assert j.status_code == 201 and j.json()["estado"] == "pendiente"

    reloj(en_hora(LUNES, 23, 59))
    assert cerrar_dia(client, h_admin)["multas"] == 0  # queda en espera de la revisión
    r = client.post(f"{J}/{j.json()['id']}/revisar", json={"aprobar": True}, headers=h_admin)
    assert r.status_code == 200 and r.json()["estado"] == "aprobada"
    fila = ver_planilla(client, h_admin, sesion["id"])[familia["hija"]["id"]]
    assert fila["asistencia"] == "justificado" and fila["multa"] is None


def test_justificacion_rechazada_despues_del_cierre_genera_la_multa(client, h_admin, familia, reloj):
    sesion = crear_sesion(client, h_admin)
    j = justificar(client, familia["h"], sesion["id"], familia["hija"]["id"]).json()
    reloj(en_hora(LUNES, 23, 59))
    cerrar_dia(client, h_admin)
    assert client.post(f"{J}/{j['id']}/revisar", json={"aprobar": False}, headers=h_admin).status_code == 422
    r = client.post(f"{J}/{j['id']}/revisar", json={"aprobar": False, "comentario": "Sin soporte"}, headers=h_admin)
    assert r.json()["estado"] == "rechazada"
    fila = ver_planilla(client, h_admin, sesion["id"])[familia["hija"]["id"]]
    assert fila["asistencia"] == "ausente" and fila["multa"] == "pendiente"


def test_justificacion_tardia_aprobada_anula_la_multa(client, h_admin, familia, reloj):
    sesion = crear_sesion(client, h_admin)
    reloj(en_hora(LUNES, 23, 59))
    cerrar_dia(client, h_admin)
    reloj(en_hora(LUNES + timedelta(days=2), 9))  # dentro de los 3 días
    j = justificar(client, familia["h"], sesion["id"], familia["hija"]["id"]).json()
    client.post(f"{J}/{j['id']}/revisar", json={"aprobar": True}, headers=h_admin)
    multa = client.get(M, headers=h_admin).json()[0]
    assert multa["estado"] == "anulada" and multa["motivo_anulacion"] == "Justificación aprobada"


def test_plazo_para_justificar_vence_para_el_miembro_pero_no_para_el_staff(client, h_admin, familia, reloj):
    sesion = crear_sesion(client, h_admin)
    reloj(en_hora(LUNES + timedelta(days=4), 9))
    r = justificar(client, familia["h"], sesion["id"], familia["hija"]["id"])
    assert r.status_code == 422 and "venció" in r.json()["detail"]
    assert justificar(client, h_admin, sesion["id"], familia["hija"]["id"]).status_code == 201


def test_justificacion_no_se_duplica_ni_aplica_a_quien_estuvo_presente(client, h_admin, familia):
    sesion = crear_sesion(client, h_admin)
    assert justificar(client, familia["h"], sesion["id"], familia["hija"]["id"]).status_code == 201
    assert justificar(client, familia["h"], sesion["id"], familia["hija"]["id"]).status_code == 409
    otra = alumno_inscrito(client, h_admin, documento="2000000009")
    marcar_asistencia(client, h_admin, sesion["id"], (otra["id"], "presente"))
    assert justificar(client, h_admin, sesion["id"], otra["id"]).status_code == 409


def test_solo_el_staff_revisa_y_el_motivo_no_va_a_la_auditoria(
    client, h_admin, familia, crear_usuario, auth_header, db
):
    sesion = crear_sesion(client, h_admin)
    motivo = "Hospitalización por apendicitis"
    j = justificar(client, familia["h"], sesion["id"], familia["hija"]["id"], motivo=motivo).json()
    crear_usuario("coach@club.com", "ENTRENADOR", rama="femenina")
    for h in (familia["h"], auth_header("coach@club.com")):
        assert client.post(f"{J}/{j['id']}/revisar", json={"aprobar": True}, headers=h).status_code == 403
    assert all(motivo not in json.dumps([a.antes, a.despues]) for a in db.scalars(select(Auditoria)))
    # El acudiente sí ve su propia justificación.
    assert [x["id"] for x in client.get(J, headers=familia["h"]).json()] == [j["id"]]


# ---------- Corrección ----------
def test_correccion_ajusta_la_multa_y_es_solo_del_admin(client, h_admin, crear_usuario, auth_header, reloj):
    alumna = alumno_inscrito(client, h_admin)
    sesion = crear_sesion(client, h_admin)
    url = f"{S}/{sesion['id']}/asistencia/{alumna['id']}"
    cuerpo = {"estado": "presente", "motivo": "Llegó tarde y no la marcaron"}
    assert client.patch(url, json=cuerpo, headers=h_admin).status_code == 422  # aún no cierra

    reloj(en_hora(LUNES, 23, 59))
    cerrar_dia(client, h_admin)
    crear_usuario("coach@club.com", "ENTRENADOR", rama="femenina")
    assert client.patch(url, json=cuerpo, headers=auth_header("coach@club.com")).status_code == 403

    r = client.patch(url, json=cuerpo, headers=h_admin)
    assert r.status_code == 200 and r.json()[0]["asistencia"] == "presente" and r.json()[0]["multa"] is None
    r = client.patch(url, json={"estado": "ausente", "motivo": "Revisado con el video del entreno"}, headers=h_admin)
    assert r.json()[0]["multa"] == "pendiente"


# ---------- Cancelación ----------
def test_cancelar_una_sesion_cerrada_anula_sus_multas_y_una_cancelada_no_multa(client, h_admin, reloj):
    alumno_inscrito(client, h_admin)
    cerrada = crear_sesion(client, h_admin)
    cancelada_antes = crear_sesion(client, h_admin, inicio="06:00", fin="07:00")
    client.post(f"{S}/{cancelada_antes['id']}/cancelar", json={"motivo": "Coliseo cerrado"}, headers=h_admin)
    reloj(en_hora(LUNES, 23, 59))
    assert cerrar_dia(client, h_admin)["multas"] == 1  # solo la de la sesión que no se canceló

    r = client.post(f"{S}/{cerrada['id']}/cancelar", json={"motivo": "Se suspendió por lluvia"}, headers=h_admin)
    assert r.status_code == 200 and r.json()["cancelada"] is True
    assert [m["estado"] for m in client.get(M, headers=h_admin).json()] == ["anulada"]


def test_deshacer_una_cancelacion_antes_del_cierre(client, h_admin, familia, crear_usuario, auth_header, reloj, db):
    sesion = crear_sesion(client, h_admin)
    url = f"{S}/{sesion['id']}/reactivar"
    assert client.post(url, headers=h_admin).status_code == 409  # no está cancelada
    client.post(f"{S}/{sesion['id']}/cancelar", json={"motivo": "Cancelada por error"}, headers=h_admin)

    crear_usuario("coach@club.com", "ENTRENADOR", rama="femenina")
    for h in (auth_header("coach@club.com"), familia["h"]):
        assert client.post(url, headers=h).status_code == 403
    r = client.post(url, headers=h_admin)
    assert r.status_code == 200
    assert (r.json()["cancelada"], r.json()["causa_cancelacion"], r.json()["motivo_cancelacion"]) == (False, None, None)
    accion = db.scalars(select(Auditoria).where(Auditoria.accion == "sesion.reactivar")).one()
    assert accion.antes["motivo"] == "Cancelada por error"
    # Vuelve a contar: al cierre genera la ausencia y la multa.
    reloj(en_hora(LUNES, 23, 59))
    assert cerrar_dia(client, h_admin)["multas"] == 1


def test_no_se_deshace_tras_el_cierre_ni_si_la_cancelo_un_torneo(client, h_admin, reloj, db):
    sesion = crear_sesion(client, h_admin)
    client.post(f"{S}/{sesion['id']}/cancelar", json={"motivo": "Lluvia fuerte"}, headers=h_admin)
    reloj(en_hora(LUNES, 23, 59))
    r = client.post(f"{S}/{sesion['id']}/reactivar", headers=h_admin)
    assert r.status_code == 422 and "cierre" in r.json()["detail"]

    otra = crear_sesion(client, h_admin, dia=LUNES + timedelta(days=2))
    db.execute(update(Sesion).where(Sesion.id == otra["id"]).values(
        cancelada=True, causa_cancelacion="torneo", motivo_cancelacion="Torneo: Copa"))
    db.commit()
    r = client.post(f"{S}/{otra['id']}/reactivar", headers=h_admin)
    assert r.status_code == 422 and "torneo" in r.json()["detail"]


# ---------- Multas: pago y anulación ----------
@pytest.fixture
def multa(client, h_admin, familia, reloj):
    crear_sesion(client, h_admin)
    reloj(en_hora(LUNES, 23, 59))
    cerrar_dia(client, h_admin)
    reloj(en_hora(LUNES + timedelta(days=1), 9))
    return client.get(M, headers=h_admin).json()[0]


def test_admin_registra_el_pago_de_una_multa(client, h_admin, multa):
    r = client.post(f"{M}/{multa['id']}/pago", json={"fecha_pago": (LUNES + timedelta(days=1)).isoformat()},
                    headers=h_admin)
    assert r.status_code == 200 and r.json()["estado"] == "pagada"
    assert client.post(f"{M}/{multa['id']}/pago", json={"fecha_pago": LUNES.isoformat()},
                       headers=h_admin).status_code == 409
    r = client.post(f"{M}/{multa['id']}/anular", json={"motivo": "Se registró por error"}, headers=h_admin)
    assert r.status_code == 409  # una pagada no se anula


def test_entrenador_no_cobra_multas_y_el_miembro_solo_ve_las_suyas(client, h_admin, multa, familia,
                                                                   crear_usuario, auth_header):
    crear_usuario("coach@club.com", "ENTRENADOR", rama="femenina")
    h_coach = auth_header("coach@club.com")
    pago = {"fecha_pago": (LUNES + timedelta(days=1)).isoformat()}
    assert client.post(f"{M}/{multa['id']}/pago", json=pago, headers=h_coach).status_code == 403
    assert client.post(f"{M}/{multa['id']}/pago", json=pago, headers=familia["h"]).status_code == 403
    assert [m["id"] for m in client.get(M, headers=familia["h"]).json()] == [multa["id"]]
    assert [m["id"] for m in client.get(M, headers=h_coach).json()] == [multa["id"]]  # es de su rama


def test_anular_multa_exige_permiso_pero_no_motivo(client, h_admin, multa, familia):
    url = f"{M}/{multa['id']}/anular"
    assert client.post(url, json={}, headers=familia["h"]).status_code == 403
    r = client.post(url, json={}, headers=h_admin)  # el motivo es opcional
    assert r.status_code == 200 and r.json()["estado"] == "anulada" and r.json()["motivo_anulacion"] is None


def test_pago_de_multa_con_fecha_futura_se_rechaza(client, h_admin, multa):
    r = client.post(f"{M}/{multa['id']}/pago", json={"fecha_pago": (LUNES + timedelta(days=5)).isoformat()},
                    headers=h_admin)
    assert r.status_code == 422


# ---------- Alertas de inasistencias seguidas ----------
def test_alerta_con_cuatro_ausencias_seguidas_y_la_justificada_rompe_la_racha(client, h_admin, reloj):
    faltona = alumno_inscrito(client, h_admin)
    juiciosa = alumno_inscrito(client, h_admin, documento="2000000003")
    for n in range(4):
        crear_sesion(client, h_admin, dia=LUNES + timedelta(days=n))
    sesiones = client.get(S, headers=h_admin).json()
    # La "juiciosa" justifica la última; la "faltona" no hace nada.
    justificar(client, h_admin, sesiones[-1]["id"], juiciosa["id"])
    j = client.get(J, headers=h_admin).json()[0]
    client.post(f"{J}/{j['id']}/revisar", json={"aprobar": True}, headers=h_admin)

    reloj(en_hora(LUNES + timedelta(days=3), 23, 59))
    assert cerrar_dia(client, h_admin)["sesiones"] == 4
    alertas = client.get(f"{S}/alertas", headers=h_admin).json()
    assert [(a["alumno_id"], a["inasistencias_seguidas"]) for a in alertas] == [(faltona["id"], 4)]


# ---------- Historial por alumno ----------
def test_historial_del_alumno_con_multas_y_alcance(client, h_admin, reloj, familia, crear_usuario, auth_header):
    hija = familia["hija"]
    otra = alumno_inscrito(client, h_admin, documento="2000000009", rama="masculina")
    sesion = crear_sesion(client, h_admin)
    marcar_asistencia(client, h_admin, sesion["id"], (otra["id"], "presente"))
    reloj(en_hora(LUNES, 23, 59))
    cerrar_dia(client, h_admin)

    r = client.get(f"/api/v1/alumnos/{hija['id']}/asistencia", headers=familia["h"])
    assert r.status_code == 200, r.text
    assert [(f["fecha"], f["estado"], f["multa_valor"], f["multa_estado"]) for f in r.json()] == [
        (LUNES.isoformat(), "ausente", 2000, "pendiente")
    ]
    presente = client.get(f"/api/v1/alumnos/{otra['id']}/asistencia", headers=h_admin).json()
    assert [(f["estado"], f["multa_valor"]) for f in presente] == [("presente", None)]

    # La familia no ve el historial de otro alumno, ni un entrenador el de otra rama: 404.
    assert client.get(f"/api/v1/alumnos/{otra['id']}/asistencia", headers=familia["h"]).status_code == 404
    crear_usuario("coach@club.com", "ENTRENADOR", rama="femenina")
    h_coach = auth_header("coach@club.com")
    assert client.get(f"/api/v1/alumnos/{otra['id']}/asistencia", headers=h_coach).status_code == 404
    assert client.get(f"/api/v1/alumnos/{hija['id']}/asistencia", headers=h_coach).status_code == 200


def test_pago_de_varias_multas_es_todo_o_nada(client, h_admin, familia, reloj, crear_usuario, auth_header):
    otra = alumno_inscrito(client, h_admin, documento="2000000005", rama="masculina")
    for dia in (LUNES, LUNES + timedelta(days=2)):
        crear_sesion(client, h_admin, dia=dia)
        reloj(en_hora(dia, 23, 59))
        cerrar_dia(client, h_admin)
    reloj(en_hora(LUNES + timedelta(days=3), 9))
    multas = client.get(M, params={"estado": "pendiente"}, headers=h_admin).json()
    assert len(multas) == 4 and {m["rama"] for m in multas} == {"femenina", "masculina"}
    de_la_hija = [m["id"] for m in multas if m["alumno_id"] == familia["hija"]["id"]]
    hoy_ = (LUNES + timedelta(days=3)).isoformat()

    # Si una ya está pagada, no se cobra ninguna (todo o nada).
    assert client.post(f"{M}/{de_la_hija[0]}/pago", json={"fecha_pago": hoy_}, headers=h_admin).status_code == 200
    r = client.post(f"{M}/pagos", json={"multa_ids": de_la_hija, "fecha_pago": hoy_}, headers=h_admin)
    assert r.status_code == 409
    assert client.get(f"{M}", params={"estado": "pendiente", "alumno_id": familia["hija"]["id"]},
                      headers=h_admin).json()[0]["id"] == de_la_hija[1]

    # El entrenador no cobra multas (403); el Admin cobra las de varios alumnos en un solo paso.
    crear_usuario("coach@club.com", "ENTRENADOR", rama="femenina")
    r = client.post(f"{M}/pagos", json={"multa_ids": [de_la_hija[1]], "fecha_pago": hoy_},
                    headers=auth_header("coach@club.com"))
    assert r.status_code == 403
    de_otra = [m["id"] for m in multas if m["alumno_id"] == otra["id"]]
    r = client.post(f"{M}/pagos", json={"multa_ids": [*de_otra, de_la_hija[1]], "fecha_pago": hoy_}, headers=h_admin)
    assert r.status_code == 200 and {m["estado"] for m in r.json()} == {"pagada"} and len(r.json()) == 3
    assert client.post(f"{M}/pagos", json={"multa_ids": [], "fecha_pago": hoy_}, headers=h_admin).status_code == 422


# ---------- Eliminar sesiones ----------
def test_solo_se_eliminan_las_sesiones_extra(client, h_admin, familia, reloj, db, crear_usuario, auth_header):
    extra = crear_sesion(client, h_admin)
    reloj(en_hora(LUNES, 23, 59))
    cerrar_dia(client, h_admin)  # deja asistencia y multa
    crear_usuario("coach@club.com", "ENTRENADOR", rama="femenina")
    assert client.delete(f"{S}/{extra['id']}", headers=auth_header("coach@club.com")).status_code == 403
    assert client.delete(f"{S}/{extra['id']}", headers=h_admin).status_code == 204
    assert client.get(f"{S}/{extra['id']}", headers=h_admin).status_code == 404
    assert client.get(M, headers=h_admin).json() == []  # su multa también

    # Las del horario (automáticas) no se eliminan: se cancelan.
    db.execute(update(Sesion).values(automatica=True))
    otra = crear_sesion(client, h_admin, dia=LUNES + timedelta(days=2))
    db.execute(update(Sesion).where(Sesion.id == otra["id"]).values(automatica=True))
    db.commit()
    r = client.delete(f"{S}/{otra['id']}", headers=h_admin)
    assert r.status_code == 422 and "cancélalo" in r.json()["detail"]


def test_una_sesion_con_multas_pagadas_no_se_elimina(client, h_admin, familia, reloj):
    extra = crear_sesion(client, h_admin)
    reloj(en_hora(LUNES, 23, 59))
    cerrar_dia(client, h_admin)
    multa = client.get(M, headers=h_admin).json()[0]
    client.post(f"{M}/{multa['id']}/pago", json={"fecha_pago": LUNES.isoformat()}, headers=h_admin)
    r = client.delete(f"{S}/{extra['id']}", headers=h_admin)
    assert r.status_code == 409 and "pagadas" in r.json()["detail"]
