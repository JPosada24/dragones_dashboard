"""Datos y acciones de prueba reutilizables (alumnos, sesiones, rifas, torneos). Las fixtures están en conftest."""
from datetime import date, datetime, timedelta

from app.core import fechas
from app.core.fechas import hoy

A = "/api/v1/alumnos"
AC = "/api/v1/acudientes"
I = "/api/v1/inscripciones"  # noqa: E741
S = "/api/v1/sesiones"
J = "/api/v1/justificaciones"
M = "/api/v1/multas"
R = "/api/v1/rifas"
T = "/api/v1/torneos"

# Lunes de referencia de las pruebas con reloj simulado (ver la fixture "reloj").
LUNES = date(2026, 11, 2)
SORTEO = LUNES + timedelta(days=10)
INICIO = LUNES + timedelta(days=20)  # inicio del torneo de prueba

PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


def nacido_hace(anios: int) -> str:
    return date(hoy().year - anios, 1, 1).isoformat()


def datos_acudiente(documento: str = "1000000001", **extra) -> dict:
    return {
        "nombres": "Marta", "apellidos": "Gómez", "tipo_documento": "CC", "documento": documento,
        "telefono": "3001234567", **extra,
    }


def datos_alumno(documento: str = "1000000002", anios: int = 20, rama: str = "femenina", **extra) -> dict:
    return {
        "nombres": "Laura", "apellidos": "Pérez", "tipo_documento": "CC" if anios >= 18 else "TI",
        "documento": documento, "fecha_nacimiento": nacido_hace(anios), "rama": rama, **extra,
    }


def crear_acudiente(client, h, **kw) -> dict:
    r = client.post(AC, json=datos_acudiente(**kw), headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def crear_alumno(client, h, **kw) -> dict:
    r = client.post(A, json=datos_alumno(**kw), headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def crear_menor(client, h, documento: str = "1000000003", acudiente: dict | None = None, **kw) -> dict:
    acudiente = acudiente or crear_acudiente(client, h, documento=f"9{documento}")
    vinculo = [{"acudiente_id": acudiente["id"], "parentesco": "madre"}]
    return crear_alumno(client, h, documento=documento, anios=12, acudientes=vinculo, **kw)


def inscribir(client, h, alumno_id: str, fecha: date | None = None):
    cuerpo = {"alumno_id": alumno_id} | ({"fecha_inscripcion": fecha.isoformat()} if fecha else {})
    return client.post(I, json=cuerpo, headers=h)


# ---------- Asistencia ----------
def en_hora(dia: date, hh: int, mm: int = 0) -> datetime:
    return datetime(dia.year, dia.month, dia.day, hh, mm, tzinfo=fechas.ZONA_CLUB)


def crear_sesion(client, h, dia=LUNES, inicio="18:00", fin="20:00"):
    r = client.post(S, json={"fecha": dia.isoformat(), "hora_inicio": inicio, "hora_fin": fin}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def alumno_inscrito(client, h, documento="1000000002", rama="femenina", **kw):
    alumno = crear_alumno(client, h, documento=documento, rama=rama, **kw)
    assert inscribir(client, h, alumno["id"]).status_code == 201
    return alumno


def marcar_asistencia(client, h, sesion_id, *marcas):
    return client.post(
        f"{S}/{sesion_id}/asistencia", json={"marcas": [{"alumno_id": a, "estado": e} for a, e in marcas]}, headers=h
    )


def cerrar_dia(client, h):
    r = client.post(f"{S}/cerrar", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def ver_planilla(client, h, sesion_id):
    return {f["alumno_id"]: f for f in client.get(f"{S}/{sesion_id}/asistencia", headers=h).json()}


def justificar(client, h, sesion_id, alumno_id, motivo="Cita médica con soporte de la EPS"):
    return client.post(f"{S}/{sesion_id}/justificaciones", json={"alumno_id": alumno_id, "motivo": motivo}, headers=h)


# ---------- Rifas y torneos ----------
def crear_rifa(client, h, nombre="Rifa de noviembre", fecha=SORTEO, anio=None):
    cuerpo = {
        "nombre": nombre, "anio": anio or fecha.year, "premio": "Balón oficial", "fecha_sorteo": fecha.isoformat(),
    }
    return client.post(R, json=cuerpo, headers=h)


def crear_torneo(client, h, **extra):
    cuerpo = {
        "nombre": "Copa Dragones", "rama": "femenina", "fecha_inicio": INICIO.isoformat(),
        "fecha_fin": (INICIO + timedelta(days=1)).isoformat(),
        "fecha_limite_inscripcion": (INICIO - timedelta(days=5)).isoformat(), "valor_inscripcion": 150000,
        **extra,
    }
    return client.post(T, json=cuerpo, headers=h)


def inscribir_equipo(client, h, torneo_id, club="Club Halcones", **extra):
    cuerpo = {"nombre_club": club, "ciudad": "Medellín", "delegado_nombre": "Ana Ruiz",
              "delegado_telefono": "3101234567", **extra}
    return client.post(f"{T}/{torneo_id}/equipos", json=cuerpo, headers=h)
