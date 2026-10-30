from datetime import date, timedelta

from app import worker
from app.core import festivos
from tests.fabrica import LUNES, S, T, en_hora, justificar

H = f"{S}/horario"
MIERCOLES = LUNES + timedelta(days=2)  # 4 nov 2026
HORARIO = {"dias": [
    {"dia_semana": 0, "hora_inicio": "18:00", "hora_fin": "20:00"},
    {"dia_semana": 2, "hora_inicio": "18:00", "hora_fin": "20:00", "lugar": "Coliseo"},
    {"dia_semana": 5, "hora_inicio": "16:00", "hora_fin": "18:00"},
]}


def _sesiones(client, h, desde=LUNES, hasta=LUNES + timedelta(days=90)):
    r = client.get(S, params={"desde": desde.isoformat(), "hasta": hasta.isoformat(), "limit": 500}, headers=h)
    return {s["fecha"]: s for s in r.json()}


# ---------- Festivos de Colombia ----------
def test_festivos_2026_coinciden_con_el_calendario_oficial():
    oficiales = {
        "2026-01-01", "2026-01-12", "2026-03-23", "2026-04-02", "2026-04-03", "2026-05-01", "2026-05-18",
        "2026-06-08", "2026-06-15", "2026-06-29", "2026-07-20", "2026-08-07", "2026-08-17", "2026-10-12",
        "2026-11-02", "2026-11-16", "2026-12-08", "2026-12-25",
    }
    assert {d.isoformat() for d in festivos.festivos(2026)} == oficiales
    assert festivos.domingo_de_pascua(2027) == date(2027, 3, 28)
    assert festivos.festivo(date(2027, 3, 22)) == "San José"  # 19 de marzo (viernes) pasa al lunes
    assert festivos.festivo(date(2026, 11, 3)) is None


# ---------- Horario y generación ----------
def test_el_horario_genera_sesiones_desde_manana_y_cancela_los_festivos(client, h_admin, reloj):
    r = client.put(H, json=HORARIO, headers=h_admin)
    assert r.status_code == 200, r.text
    assert [d["dia_semana"] for d in r.json()["dias"]] == [0, 2, 5]
    sesiones = _sesiones(client, h_admin)
    assert LUNES.isoformat() not in sesiones  # la de hoy nunca se crea sola
    assert {date.fromisoformat(f).weekday() for f in sesiones} == {0, 2, 5}
    assert max(sesiones) <= (LUNES + timedelta(days=60)).isoformat()
    miercoles = sesiones[MIERCOLES.isoformat()]
    assert miercoles["automatica"] and miercoles["lugar"] == "Coliseo" and not miercoles["cancelada"]
    assert sesiones["2026-11-07"]["hora_inicio"] == "16:00:00"  # sábado
    festivo = sesiones["2026-11-16"]  # Independencia de Cartagena (lunes)
    assert festivo["cancelada"] and festivo["causa_cancelacion"] == "festivo"
    assert festivo["motivo_cancelacion"] == "Festivo: Independencia de Cartagena"


def test_la_programacion_es_idempotente(client, h_admin, reloj):
    client.put(H, json=HORARIO, headers=h_admin)
    tarea = next(t for t in worker.tareas() if t.nombre == "programar_sesiones")
    assert worker.ejecutar(tarea) is None
    total = len(_sesiones(client, h_admin))
    reloj(en_hora(LUNES + timedelta(days=7), 10))  # una semana después aparece la semana siguiente
    assert worker.ejecutar(tarea) == "3 sesiones creadas, 0 canceladas, 0 reactivadas"
    assert len(_sesiones(client, h_admin)) == total + 3


def test_cambiar_el_horario_reprograma_y_conserva_lo_que_tiene_registros(client, h_admin, familia, reloj):
    client.put(H, json=HORARIO, headers=h_admin)
    miercoles = _sesiones(client, h_admin)[MIERCOLES.isoformat()]
    justificar(client, familia["h"], miercoles["id"], familia["hija"]["id"])  # ya tiene una justificación

    nuevo = {"dias": [
        {"dia_semana": 0, "hora_inicio": "18:00", "hora_fin": "21:00"},  # mismo inicio: solo se ajusta
        {"dia_semana": 1, "hora_inicio": "18:00", "hora_fin": "20:00"},  # martes en vez de miércoles
    ]}
    r = client.put(H, json=nuevo, headers=h_admin).json()
    assert r["canceladas"] == 1 and r["eliminadas"] > 0
    sesiones = _sesiones(client, h_admin)
    assert sesiones["2026-11-09"]["hora_fin"] == "21:00:00"
    assert "2026-11-03" in sesiones  # mañana es martes: la programación empieza desde mañana
    conservada = sesiones[MIERCOLES.isoformat()]
    assert conservada["cancelada"] and conservada["causa_cancelacion"] == "horario"
    assert "2026-11-07" not in sesiones and "2026-11-10" in sesiones  # ya no hay sábados; sí martes
    # Si el miércoles vuelve al horario, la sesión conservada se reactiva.
    client.put(H, json=HORARIO, headers=h_admin)
    assert not _sesiones(client, h_admin)[MIERCOLES.isoformat()]["cancelada"]


def test_un_torneo_cancela_los_entrenamientos_y_vuelven_si_se_cancela(client, h_admin, reloj):
    client.put(H, json=HORARIO, headers=h_admin)
    inicio = LUNES + timedelta(days=9)  # miércoles 11 nov
    torneo = client.post(T, json={
        "nombre": "Copa Dragones", "rama": "femenina", "fecha_inicio": inicio.isoformat(),
        "fecha_fin": (inicio + timedelta(days=3)).isoformat(),
        "fecha_limite_inscripcion": (inicio - timedelta(days=2)).isoformat(), "valor_inscripcion": 150000,
    }, headers=h_admin).json()
    sesiones = _sesiones(client, h_admin)
    for f in ("2026-11-11", "2026-11-14"):
        assert sesiones[f]["causa_cancelacion"] == "torneo"
        assert sesiones[f]["motivo_cancelacion"] == "Torneo: Copa Dragones"
    assert not sesiones["2026-11-09"]["cancelada"]

    client.post(f"{T}/{torneo['id']}/cancelar", json={"motivo": "Coliseo en obras"}, headers=h_admin)
    sesiones = _sesiones(client, h_admin)
    assert not sesiones["2026-11-11"]["cancelada"] and not sesiones["2026-11-14"]["cancelada"]
    assert sesiones["2026-11-16"]["causa_cancelacion"] == "festivo"  # el festivo sigue cancelado


# ---------- Permisos ----------
def test_solo_admin_y_superadmin_cambian_el_horario(client, h_admin, h_root, familia, crear_usuario, auth_header):
    crear_usuario("coach@club.com", "ENTRENADOR")
    for h in (auth_header("coach@club.com"), familia["h"]):
        assert client.put(H, json=HORARIO, headers=h).status_code == 403
        assert client.get(H, headers=h).status_code == 200  # todos pueden consultar el horario
    assert client.put(H, json={"dias": []}, headers=h_root).status_code == 200


def test_horario_invalido(client, h_admin):
    repetido = {"dias": [HORARIO["dias"][0], HORARIO["dias"][0]]}
    assert client.put(H, json=repetido, headers=h_admin).status_code == 422
    malo = {"dias": [{"dia_semana": 7, "hora_inicio": "18:00", "hora_fin": "20:00"}]}
    assert client.put(H, json=malo, headers=h_admin).status_code == 422
    al_reves = {"dias": [{"dia_semana": 0, "hora_inicio": "20:00", "hora_fin": "18:00"}]}
    assert client.put(H, json=al_reves, headers=h_admin).status_code == 422
