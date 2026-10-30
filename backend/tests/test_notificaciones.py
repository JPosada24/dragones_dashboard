from datetime import timedelta

import pytest
from sqlalchemy import select

from app import worker
from app.core import fechas
from app.core.correo import correo_registro
from app.models.notificaciones import Notificacion
from app.services import notificaciones
from tests.fabrica import (
    LUNES,
    J,
    cerrar_dia,
    crear_acudiente,
    crear_menor,
    crear_sesion,
    en_hora,
    inscribir,
    justificar,
)

N = "/api/v1/notificaciones"


@pytest.fixture(autouse=True)
def _correo_limpio():
    correo_registro().enviados.clear()


def _tarea(nombre):
    return next(t for t in worker.tareas() if t.nombre == nombre)


def _multa_para_la_familia(client, h_admin, reloj):
    crear_sesion(client, h_admin)
    reloj(en_hora(LUNES, 23, 59))
    cerrar_dia(client, h_admin)


# ---------- Avisos por evento ----------
def test_una_multa_avisa_a_la_familia_por_bandeja_correo_y_whatsapp(client, h_admin, familia, reloj, db):
    _multa_para_la_familia(client, h_admin, reloj)
    [aviso] = client.get(f"{N}/mias", headers=familia["h"]).json()
    assert aviso["tipo"] == "multa" and aviso["leida"] is False
    assert "$2.000" in aviso["mensaje"] and "05/11/2026" in aviso["mensaje"]  # plazo para justificar (3 días)
    fila = db.scalar(select(Notificacion))
    assert fila.email_destino == "padre@club.com" and fila.email_estado == "pendiente"
    assert fila.whatsapp_estado == "pendiente" and fila.telefono_destino == "3001234567"


def test_el_worker_envia_los_correos_pendientes(client, h_admin, familia, reloj):
    _multa_para_la_familia(client, h_admin, reloj)
    assert worker.ejecutar(_tarea("enviar_correos")) == "1 correos enviados, 0 fallidos definitivamente"
    [(destino, asunto, cuerpo)] = correo_registro().enviados
    assert destino == "padre@club.com" and asunto == "[Club Dragones] Multa por inasistencia"
    assert cuerpo.startswith("Hola Marta.") and cuerpo.endswith("— Club Dragones")
    assert worker.ejecutar(_tarea("enviar_correos")) is None  # no se reenvía


def test_un_correo_que_falla_se_reintenta_y_luego_queda_fallido(client, h_admin, familia, reloj, db):
    _multa_para_la_familia(client, h_admin, reloj)

    class CorreoCaido:
        def enviar(self, *_):
            raise ConnectionError("SMTP no responde")

    momento = fechas.ahora()
    for intento in range(1, notificaciones.MAX_INTENTOS_CORREO + 1):
        notificaciones.enviar_correos(db, CorreoCaido(), ahora=momento)
        db.commit()
        fila = db.scalar(select(Notificacion))
        assert fila.email_intentos == intento
        # Antes del próximo intento no se vuelve a probar.
        assert notificaciones.enviar_correos(db, CorreoCaido(), ahora=momento) == (0, 0)
        momento += timedelta(minutes=2 ** intento + 1)
    assert fila.email_estado == "fallido" and "SMTP no responde" in fila.email_error


def test_justificacion_rechazada_avisa_con_el_motivo(client, h_admin, familia):
    sesion = crear_sesion(client, h_admin)
    j = justificar(client, familia["h"], sesion["id"], familia["hija"]["id"]).json()
    client.post(f"{J}/{j['id']}/revisar", json={"aprobar": False, "comentario": "Sin soporte médico"}, headers=h_admin)
    [aviso] = client.get(f"{N}/mias", headers=familia["h"]).json()
    assert aviso["titulo"] == "Justificación rechazada" and "Sin soporte médico" in aviso["mensaje"]
    # La justificación no va por WhatsApp.
    assert client.get(f"{N}/whatsapp", headers=h_admin).json() == []


def test_inscripcion_vencida_avisa_a_la_familia(client, h_admin, familia, reloj):
    reloj(en_hora(LUNES + timedelta(days=31), 9))
    worker.ejecutar(_tarea("vencer_inscripciones"))
    tipos = [a["tipo"] for a in client.get(f"{N}/mias", headers=familia["h"]).json()]
    assert tipos == ["inscripcion_vencida"]


# ---------- Avisos programados ----------
def test_recordatorios_de_pago_7_y_1_dia_antes_sin_duplicar(client, h_admin, familia, reloj):
    tarea = _tarea("avisos_programados")
    reloj(en_hora(LUNES + timedelta(days=22), 9))  # faltan 8 días: aún no
    assert worker.ejecutar(tarea) is None
    reloj(en_hora(LUNES + timedelta(days=23), 9))  # faltan 7
    assert worker.ejecutar(tarea) == "1 recordatorios de pago, 0 alertas de inasistencia"
    assert worker.ejecutar(tarea) is None  # idempotente
    reloj(en_hora(LUNES + timedelta(days=29), 9))  # falta 1
    worker.ejecutar(tarea)
    mensajes = [a["mensaje"] for a in client.get(f"{N}/mias", headers=familia["h"]).json()]
    assert len(mensajes) == 2 and "vence mañana" in mensajes[0] and "en 7 días" in mensajes[1]
    assert all("$90.000" in m for m in mensajes)


def test_alerta_de_inasistencias_llega_al_staff_una_vez_por_racha(client, h_admin, familia, reloj, auth_header):
    for n in range(4):
        crear_sesion(client, h_admin, dia=LUNES + timedelta(days=n))
    reloj(en_hora(LUNES + timedelta(days=3), 23, 59))
    cerrar_dia(client, h_admin)
    tarea = _tarea("avisos_programados")
    assert worker.ejecutar(tarea) == "0 recordatorios de pago, 1 alertas de inasistencia"
    assert worker.ejecutar(tarea) is None
    [alerta] = [a for a in client.get(f"{N}/mias", headers=h_admin).json() if a["tipo"] == "alerta_inasistencia"]
    assert "4 inasistencias seguidas" in alerta["mensaje"]
    # La familia no recibe la alerta del staff (sí recibe sus 4 multas).
    assert {a["tipo"] for a in client.get(f"{N}/mias", headers=familia["h"]).json()} == {"multa"}


# ---------- Bandeja ----------
def test_cada_quien_ve_y_marca_solo_sus_avisos(client, h_admin, familia, reloj, crear_usuario, auth_header):
    _multa_para_la_familia(client, h_admin, reloj)
    [aviso] = client.get(f"{N}/mias", headers=familia["h"]).json()
    crear_usuario("otro@club.com", "MIEMBRO")
    h_otro = auth_header("otro@club.com")
    assert client.get(f"{N}/mias", headers=h_otro).json() == []
    assert client.post(f"{N}/{aviso['id']}/leer", headers=h_otro).status_code == 404
    assert client.post(f"{N}/{aviso['id']}/leer", headers=familia["h"]).json()["leida"] is True
    assert client.get(f"{N}/mias", params={"no_leidas": True}, headers=familia["h"]).json() == []


def test_acudiente_sin_cuenta_ni_correo_solo_recibe_lo_que_va_por_whatsapp(client, h_admin, reloj, db):
    sin_cuenta = crear_acudiente(client, h_admin, documento="7000000001")
    hija = crear_menor(client, h_admin, documento="7000000002", acudiente=sin_cuenta)
    inscribir(client, h_admin, hija["id"])
    sesion = crear_sesion(client, h_admin)
    j = justificar(client, h_admin, sesion["id"], hija["id"]).json()
    client.post(f"{J}/{j['id']}/revisar", json={"aprobar": True}, headers=h_admin)
    assert db.scalars(select(Notificacion)).all() == []  # la justificación no tiene por dónde llegarle


# ---------- WhatsApp ----------
def test_cola_de_whatsapp_con_enlace_listo_y_solo_para_el_staff(client, h_admin, familia, reloj):
    _multa_para_la_familia(client, h_admin, reloj)
    assert client.get(f"{N}/whatsapp", headers=familia["h"]).status_code == 403
    [item] = client.get(f"{N}/whatsapp", headers=h_admin).json()
    assert item["enlace"].startswith("https://wa.me/573001234567?text=Hola%20Marta.")
    r = client.post(f"{N}/{item['id']}/whatsapp", json={"accion": "enviado"}, headers=h_admin)
    assert r.status_code == 204
    assert client.get(f"{N}/whatsapp", headers=h_admin).json() == []
    assert client.post(f"{N}/{item['id']}/whatsapp", json={"accion": "enviado"}, headers=h_admin).status_code == 409


def test_enlace_whatsapp_respeta_numeros_internacionales():
    assert notificaciones.enlace_whatsapp("+34612345678", "Hola").startswith("https://wa.me/34612345678?")
    assert notificaciones.enlace_whatsapp("3001234567", "Hola y adiós").endswith("text=Hola%20y%20adi%C3%B3s")


# ---------- Correo de prueba ----------
def test_correo_de_prueba_solo_para_el_superadmin(client, h_admin, h_root):
    assert client.post(f"{N}/correo-prueba", headers=h_admin).status_code == 403
    r = client.post(f"{N}/correo-prueba", headers=h_root)
    assert r.json()["enviado"] is True and r.json()["modo"] == "registro"
    assert correo_registro().enviados[0][0] == "root@club.com"
