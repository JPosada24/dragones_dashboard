"""Datos de prueba reutilizables para alumnos, acudientes e inscripciones."""
from datetime import date

from app.core.fechas import hoy

A = "/api/v1/alumnos"
AC = "/api/v1/acudientes"
I = "/api/v1/inscripciones"  # noqa: E741

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
