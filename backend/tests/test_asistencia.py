import json
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core import fechas
from app.models.sistema import Auditoria
from tests.fabrica import crear_acudiente, crear_alumno, crear_menor, inscribir

S = "/api/v1/sesiones"
J = "/api/v1/justificaciones"
M = "/api/v1/multas"
LUNES = date(2026, 11, 2)


def _en(dia: date, hh: int, mm: int = 0) -> datetime:
    return datetime(dia.year, dia.month, dia.day, hh, mm, tzinfo=fechas.ZONA_CLUB)


@pytest.fixture
def reloj(monkeypatch):
    """Reloj simulado del club: arranca el lunes a las 10:00 y se mueve con reloj(datetime)."""
    actual = {"ahora": _en(LUNES, 10)}
    monkeypatch.setattr(fechas, "ahora", lambda: actual["ahora"])

    def mover(momento: datetime) -> None:
        actual["ahora"] = momento

    return mover


@pytest.fixture
def h_root(crear_usuario, auth_header, reloj):
    crear_usuario("root@club.com", "SUPERADMIN")
    return auth_header("root@club.com")


@pytest.fixture
def h_admin(crear_usuario, auth_header, reloj):
    crear_usuario("adm@club.com", "ADMIN")
    return auth_header("adm@club.com")


def _sesion(client, h, dia=LUNES, rama="femenina", inicio="18:00", fin="20:00"):
    r = client.post(S, json={"rama": rama, "fecha": dia.isoformat(), "hora_inicio": inicio, "hora_fin": fin}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def _alumno_inscrito(client, h, documento="1000000002", rama="femenina", **kw):
    alumno = crear_alumno(client, h, documento=documento, rama=rama, **kw)
    assert inscribir(client, h, alumno["id"]).status_code == 201
    return alumno


def _marcar(client, h, sesion_id, *marcas):
    return client.post(
        f"{S}/{sesion_id}/asistencia", json={"marcas": [{"alumno_id": a, "estado": e} for a, e in marcas]}, headers=h
    )


def _cerrar(client, h):
    r = client.post(f"{S}/cerrar", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _planilla(client, h, sesion_id):
    return {f["alumno_id"]: f for f in client.get(f"{S}/{sesion_id}/asistencia", headers=h).json()}


@pytest.fixture
def familia(client, h_admin, crear_usuario, auth_header):
    """Un acudiente con cuenta (Miembro) y su hija inscrita en la rama femenina."""
    padre = crear_usuario("padre@club.com", "MIEMBRO")
    acudiente = crear_acudiente(client, h_admin, usuario_id=str(padre.id))
    hija = crear_menor(client, h_admin, documento="3000000001", acudiente=acudiente)
    inscribir(client, h_admin, hija["id"])
    return {"hija": hija, "h": auth_header("padre@club.com")}


# ---------- Programación de sesiones ----------
def test_programar_crea_solo_los_dias_elegidos_y_no_duplica(client, h_admin):
    cuerpo = {
        "rama": "femenina", "desde": LUNES.isoformat(), "hasta": (LUNES + timedelta(days=13)).isoformat(),
        "dias_semana": [0, 2, 4], "hora_inicio": "18:00", "hora_fin": "20:00", "lugar": "Coliseo",
    }
    r = client.post(f"{S}/programar", json=cuerpo, headers=h_admin)
    assert r.status_code == 201 and len(r.json()) == 6
    assert {date.fromisoformat(s["fecha"]).weekday() for s in r.json()} == {0, 2, 4}
    assert client.post(f"{S}/programar", json=cuerpo, headers=h_admin).status_code == 409  # ya existen


def test_no_se_programan_sesiones_en_el_pasado_ni_con_horario_invalido(client, h_admin):
    assert client.post(S, json={"rama": "femenina", "fecha": (LUNES - timedelta(days=1)).isoformat(),
                                "hora_inicio": "18:00", "hora_fin": "20:00"}, headers=h_admin).status_code == 422
    assert client.post(S, json={"rama": "femenina", "fecha": LUNES.isoformat(),
                                "hora_inicio": "20:00", "hora_fin": "18:00"}, headers=h_admin).status_code == 422


def test_entrenador_programa_y_ve_solo_su_rama(client, h_admin, crear_usuario, auth_header):
    crear_usuario("coach@club.com", "ENTRENADOR", rama="femenina")
    h = auth_header("coach@club.com")
    propia = _sesion(client, h)
    r = client.post(S, json={"rama": "masculina", "fecha": LUNES.isoformat(), "hora_inicio": "18:00",
                             "hora_fin": "20:00"}, headers=h)
    assert r.status_code == 403
    ajena = _sesion(client, h_admin, rama="masculina")
    assert [s["id"] for s in client.get(S, headers=h).json()] == [propia["id"]]
    assert client.get(f"{S}/{ajena['id']}", headers=h).status_code == 404


def test_miembro_no_programa_sesiones(client, familia):
    r = client.post(S, json={"rama": "femenina", "fecha": LUNES.isoformat(), "hora_inicio": "18:00",
                             "hora_fin": "20:00"}, headers=familia["h"])
    assert r.status_code == 403


# ---------- Planilla y marcación del grupo ----------
def test_planilla_incluye_solo_inscritos_vigentes_de_la_rama(client, h_admin):
    inscrita = _alumno_inscrito(client, h_admin)
    crear_alumno(client, h_admin, documento="2000000001")  # sin inscripción
    _alumno_inscrito(client, h_admin, documento="2000000002", rama="masculina")
    sesion = _sesion(client, h_admin)
    assert list(_planilla(client, h_admin, sesion["id"])) == [inscrita["id"]]


def test_entrenador_marca_su_grupo(client, h_admin, crear_usuario, auth_header):
    alumna = _alumno_inscrito(client, h_admin)
    otra = _alumno_inscrito(client, h_admin, documento="2000000003")
    sesion = _sesion(client, h_admin)
    crear_usuario("coach@club.com", "ENTRENADOR", rama="femenina")
    h = auth_header("coach@club.com")
    r = _marcar(client, h, sesion["id"], (alumna["id"], "presente"), (otra["id"], "ausente"))
    assert r.status_code == 200
    filas = {f["alumno_id"]: f["asistencia"] for f in r.json()}
    assert filas == {alumna["id"]: "presente", otra["id"]: "ausente"}


def test_no_se_marca_a_quien_no_es_de_la_sesion_ni_una_sesion_futura(client, h_admin):
    ajeno = _alumno_inscrito(client, h_admin, documento="2000000002", rama="masculina")
    hoy_ = _sesion(client, h_admin)
    assert _marcar(client, h_admin, hoy_["id"], (ajeno["id"], "presente")).status_code == 422
    alumna = _alumno_inscrito(client, h_admin)
    futura = _sesion(client, h_admin, dia=LUNES + timedelta(days=2))
    assert _marcar(client, h_admin, futura["id"], (alumna["id"], "presente")).status_code == 422


# ---------- Cierre diario y multas ----------
def test_cierre_genera_ausencia_y_multa_solo_a_quien_no_marco_ni_justifico(client, h_admin, reloj, db):
    presente = _alumno_inscrito(client, h_admin)
    falto = _alumno_inscrito(client, h_admin, documento="2000000003")
    sesion = _sesion(client, h_admin)
    _marcar(client, h_admin, sesion["id"], (presente["id"], "presente"))

    reloj(_en(LUNES, 23, 0))  # antes de las 23:59 todavía no se cierra
    assert _cerrar(client, h_admin) == {"sesiones": 0, "ausencias": 0, "multas": 0}

    reloj(_en(LUNES, 23, 59))
    assert _cerrar(client, h_admin) == {"sesiones": 1, "ausencias": 1, "multas": 1}
    planilla = _planilla(client, h_admin, sesion["id"])
    assert planilla[presente["id"]]["multa"] is None
    assert planilla[falto["id"]]["asistencia"] == "ausente" and planilla[falto["id"]]["multa"] == "pendiente"
    multas = client.get(M, headers=h_admin).json()
    assert [(m["alumno_id"], m["valor"]) for m in multas] == [(falto["id"], 2000)]

    # Cerrar de nuevo no duplica nada.
    assert _cerrar(client, h_admin) == {"sesiones": 0, "ausencias": 0, "multas": 0}
    assert "sesion.cerrar" in {a.accion for a in db.scalars(select(Auditoria))}


def test_valor_de_la_multa_sale_de_configuracion_y_cero_las_desactiva(client, h_root, reloj):
    alumna = _alumno_inscrito(client, h_root)
    s1 = _sesion(client, h_root)
    client.patch("/api/v1/configuracion/multa_inasistencia", json={"valor": 3000}, headers=h_root)
    reloj(_en(LUNES, 23, 59))
    _cerrar(client, h_root)
    assert client.get(M, headers=h_root).json()[0]["valor"] == 3000

    reloj(_en(LUNES + timedelta(days=1), 10))
    s2 = _sesion(client, h_root, dia=LUNES + timedelta(days=1))
    client.patch("/api/v1/configuracion/multa_inasistencia", json={"valor": 0}, headers=h_root)
    reloj(_en(LUNES + timedelta(days=1), 23, 59))
    assert _cerrar(client, h_root)["multas"] == 0
    assert _planilla(client, h_root, s2["id"])[alumna["id"]]["asistencia"] == "ausente"
    assert s1["id"] != s2["id"]


def test_marcar_despues_del_cierre_exige_correccion(client, h_admin, reloj):
    alumna = _alumno_inscrito(client, h_admin)
    sesion = _sesion(client, h_admin)
    reloj(_en(LUNES, 23, 59))
    _cerrar(client, h_admin)
    r = _marcar(client, h_admin, sesion["id"], (alumna["id"], "presente"))
    assert r.status_code == 422 and "corrección" in r.json()["detail"]


# ---------- Marcación propia ----------
def test_miembro_marca_la_asistencia_de_su_hija_solo_en_el_horario(client, h_admin, familia, reloj):
    sesion = _sesion(client, h_admin)
    cuerpo = {"alumno_id": familia["hija"]["id"]}
    reloj(_en(LUNES, 17, 0))  # más de 30 min antes
    r = client.post(f"{S}/{sesion['id']}/asistencia/propia", json=cuerpo, headers=familia["h"])
    assert r.status_code == 422 and "17:30" in r.json()["detail"]
    reloj(_en(LUNES, 17, 45))
    assert client.post(f"{S}/{sesion['id']}/asistencia/propia", json=cuerpo, headers=familia["h"]).status_code == 204
    assert client.post(f"{S}/{sesion['id']}/asistencia/propia", json=cuerpo, headers=familia["h"]).status_code == 409


def test_miembro_no_marca_a_otro_alumno_ni_sobre_lo_que_marco_el_entrenador(client, h_admin, familia, reloj):
    ajena = _alumno_inscrito(client, h_admin, documento="2000000009")
    sesion = _sesion(client, h_admin)
    reloj(_en(LUNES, 18, 30))
    r = client.post(f"{S}/{sesion['id']}/asistencia/propia", json={"alumno_id": ajena["id"]}, headers=familia["h"])
    assert r.status_code == 404
    _marcar(client, h_admin, sesion["id"], (familia["hija"]["id"], "ausente"))
    r = client.post(f"{S}/{sesion['id']}/asistencia/propia", json={"alumno_id": familia["hija"]["id"]},
                    headers=familia["h"])
    assert r.status_code == 409


def test_miembro_solo_ve_su_fila_en_la_planilla(client, h_admin, familia):
    _alumno_inscrito(client, h_admin, documento="2000000009")
    sesion = _sesion(client, h_admin)
    assert list(_planilla(client, familia["h"], sesion["id"])) == [familia["hija"]["id"]]


# ---------- Justificaciones ----------
def _justificar(client, h, sesion_id, alumno_id, motivo="Cita médica con soporte de la EPS"):
    return client.post(f"{S}/{sesion_id}/justificaciones", json={"alumno_id": alumno_id, "motivo": motivo}, headers=h)


def test_justificacion_pendiente_evita_la_multa_y_si_se_aprueba_queda_justificado(client, h_admin, familia, reloj):
    sesion = _sesion(client, h_admin)
    j = _justificar(client, familia["h"], sesion["id"], familia["hija"]["id"])
    assert j.status_code == 201 and j.json()["estado"] == "pendiente"

    reloj(_en(LUNES, 23, 59))
    assert _cerrar(client, h_admin)["multas"] == 0  # queda en espera de la revisión
    r = client.post(f"{J}/{j.json()['id']}/revisar", json={"aprobar": True}, headers=h_admin)
    assert r.status_code == 200 and r.json()["estado"] == "aprobada"
    fila = _planilla(client, h_admin, sesion["id"])[familia["hija"]["id"]]
    assert fila["asistencia"] == "justificado" and fila["multa"] is None


def test_justificacion_rechazada_despues_del_cierre_genera_la_multa(client, h_admin, familia, reloj):
    sesion = _sesion(client, h_admin)
    j = _justificar(client, familia["h"], sesion["id"], familia["hija"]["id"]).json()
    reloj(_en(LUNES, 23, 59))
    _cerrar(client, h_admin)
    assert client.post(f"{J}/{j['id']}/revisar", json={"aprobar": False}, headers=h_admin).status_code == 422
    r = client.post(f"{J}/{j['id']}/revisar", json={"aprobar": False, "comentario": "Sin soporte"}, headers=h_admin)
    assert r.json()["estado"] == "rechazada"
    fila = _planilla(client, h_admin, sesion["id"])[familia["hija"]["id"]]
    assert fila["asistencia"] == "ausente" and fila["multa"] == "pendiente"


def test_justificacion_tardia_aprobada_anula_la_multa(client, h_admin, familia, reloj):
    sesion = _sesion(client, h_admin)
    reloj(_en(LUNES, 23, 59))
    _cerrar(client, h_admin)
    reloj(_en(LUNES + timedelta(days=2), 9))  # dentro de los 3 días
    j = _justificar(client, familia["h"], sesion["id"], familia["hija"]["id"]).json()
    client.post(f"{J}/{j['id']}/revisar", json={"aprobar": True}, headers=h_admin)
    multa = client.get(M, headers=h_admin).json()[0]
    assert multa["estado"] == "anulada" and multa["motivo_anulacion"] == "Justificación aprobada"


def test_plazo_para_justificar_vence_para_el_miembro_pero_no_para_el_staff(client, h_admin, familia, reloj):
    sesion = _sesion(client, h_admin)
    reloj(_en(LUNES + timedelta(days=4), 9))
    r = _justificar(client, familia["h"], sesion["id"], familia["hija"]["id"])
    assert r.status_code == 422 and "venció" in r.json()["detail"]
    assert _justificar(client, h_admin, sesion["id"], familia["hija"]["id"]).status_code == 201


def test_justificacion_no_se_duplica_ni_aplica_a_quien_estuvo_presente(client, h_admin, familia):
    sesion = _sesion(client, h_admin)
    assert _justificar(client, familia["h"], sesion["id"], familia["hija"]["id"]).status_code == 201
    assert _justificar(client, familia["h"], sesion["id"], familia["hija"]["id"]).status_code == 409
    otra = _alumno_inscrito(client, h_admin, documento="2000000009")
    _marcar(client, h_admin, sesion["id"], (otra["id"], "presente"))
    assert _justificar(client, h_admin, sesion["id"], otra["id"]).status_code == 409


def test_solo_el_staff_revisa_y_el_motivo_no_va_a_la_auditoria(client, h_admin, familia, crear_usuario, auth_header, db):
    sesion = _sesion(client, h_admin)
    motivo = "Hospitalización por apendicitis"
    j = _justificar(client, familia["h"], sesion["id"], familia["hija"]["id"], motivo=motivo).json()
    crear_usuario("coach@club.com", "ENTRENADOR", rama="femenina")
    for h in (familia["h"], auth_header("coach@club.com")):
        assert client.post(f"{J}/{j['id']}/revisar", json={"aprobar": True}, headers=h).status_code == 403
    assert all(motivo not in json.dumps([a.antes, a.despues]) for a in db.scalars(select(Auditoria)))
    # El acudiente sí ve su propia justificación.
    assert [x["id"] for x in client.get(J, headers=familia["h"]).json()] == [j["id"]]


# ---------- Corrección ----------
def test_correccion_ajusta_la_multa_y_es_solo_del_admin(client, h_admin, crear_usuario, auth_header, reloj):
    alumna = _alumno_inscrito(client, h_admin)
    sesion = _sesion(client, h_admin)
    url = f"{S}/{sesion['id']}/asistencia/{alumna['id']}"
    cuerpo = {"estado": "presente", "motivo": "Llegó tarde y no la marcaron"}
    assert client.patch(url, json=cuerpo, headers=h_admin).status_code == 422  # aún no cierra

    reloj(_en(LUNES, 23, 59))
    _cerrar(client, h_admin)
    crear_usuario("coach@club.com", "ENTRENADOR", rama="femenina")
    assert client.patch(url, json=cuerpo, headers=auth_header("coach@club.com")).status_code == 403

    r = client.patch(url, json=cuerpo, headers=h_admin)
    assert r.status_code == 200 and r.json()[0]["asistencia"] == "presente" and r.json()[0]["multa"] is None
    r = client.patch(url, json={"estado": "ausente", "motivo": "Revisado con el video del entreno"}, headers=h_admin)
    assert r.json()[0]["multa"] == "pendiente"


# ---------- Cancelación ----------
def test_cancelar_una_sesion_cerrada_anula_sus_multas_y_una_cancelada_no_multa(client, h_admin, reloj):
    _alumno_inscrito(client, h_admin)
    cerrada = _sesion(client, h_admin)
    cancelada_antes = _sesion(client, h_admin, inicio="06:00", fin="07:00")
    client.post(f"{S}/{cancelada_antes['id']}/cancelar", json={"motivo": "Coliseo cerrado"}, headers=h_admin)
    reloj(_en(LUNES, 23, 59))
    assert _cerrar(client, h_admin)["multas"] == 1  # solo la de la sesión que no se canceló

    r = client.post(f"{S}/{cerrada['id']}/cancelar", json={"motivo": "Se suspendió por lluvia"}, headers=h_admin)
    assert r.status_code == 200 and r.json()["cancelada"] is True
    assert [m["estado"] for m in client.get(M, headers=h_admin).json()] == ["anulada"]


# ---------- Multas: pago y anulación ----------
@pytest.fixture
def multa(client, h_admin, familia, reloj):
    _sesion(client, h_admin)
    reloj(_en(LUNES, 23, 59))
    _cerrar(client, h_admin)
    reloj(_en(LUNES + timedelta(days=1), 9))
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


def test_anular_multa_exige_motivo_y_permiso(client, h_admin, multa, familia):
    url = f"{M}/{multa['id']}/anular"
    assert client.post(url, json={"motivo": "Error"}, headers=h_admin).status_code == 422
    assert client.post(url, json={"motivo": "Estaba de viaje con la selección"}, headers=familia["h"]).status_code == 403
    r = client.post(url, json={"motivo": "Estaba de viaje con la selección"}, headers=h_admin)
    assert r.status_code == 200 and r.json()["estado"] == "anulada"


def test_pago_de_multa_con_fecha_futura_se_rechaza(client, h_admin, multa):
    r = client.post(f"{M}/{multa['id']}/pago", json={"fecha_pago": (LUNES + timedelta(days=5)).isoformat()},
                    headers=h_admin)
    assert r.status_code == 422


# ---------- Alertas de inasistencias seguidas ----------
def test_alerta_con_cuatro_ausencias_seguidas_y_la_justificada_rompe_la_racha(client, h_admin, reloj):
    faltona = _alumno_inscrito(client, h_admin)
    juiciosa = _alumno_inscrito(client, h_admin, documento="2000000003")
    client.post(f"{S}/programar", json={
        "rama": "femenina", "desde": LUNES.isoformat(), "hasta": (LUNES + timedelta(days=3)).isoformat(),
        "dias_semana": [0, 1, 2, 3], "hora_inicio": "18:00", "hora_fin": "20:00",
    }, headers=h_admin)
    sesiones = client.get(S, headers=h_admin).json()
    # La "juiciosa" justifica la última; la "faltona" no hace nada.
    _justificar(client, h_admin, sesiones[-1]["id"], juiciosa["id"])
    j = client.get(J, headers=h_admin).json()[0]
    client.post(f"{J}/{j['id']}/revisar", json={"aprobar": True}, headers=h_admin)

    reloj(_en(LUNES + timedelta(days=3), 23, 59))
    assert _cerrar(client, h_admin)["sesiones"] == 4
    alertas = client.get(f"{S}/alertas", headers=h_admin).json()
    assert [(a["alumno_id"], a["inasistencias_seguidas"]) for a in alertas] == [(faltona["id"], 4)]
