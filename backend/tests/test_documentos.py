from pathlib import Path

import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.models.alumnos import DocumentoAlumno
from app.models.sistema import Auditoria
from tests.fabrica import PDF, A, crear_acudiente, crear_alumno, crear_menor


@pytest.fixture
def h_admin(crear_usuario, auth_header):
    crear_usuario("adm@club.com", "ADMIN")
    return auth_header("adm@club.com")


def _subir(client, h, alumno_id, contenido=PDF, nombre="cedula.pdf", tipo="identidad"):
    return client.post(
        f"{A}/{alumno_id}/documentos", data={"tipo": tipo},
        files={"archivo": (nombre, contenido, "application/pdf")}, headers=h,
    )


def _archivo_en_disco(db, documento_id) -> Path:
    doc = db.get(DocumentoAlumno, documento_id)
    return Path(get_settings().documentos_dir) / doc.clave_almacen[:2] / doc.clave_almacen


def test_subir_y_descargar_pdf_queda_cifrado_en_disco(client, h_admin, db):
    alumno = crear_alumno(client, h_admin)
    r = _subir(client, h_admin, alumno["id"])
    assert r.status_code == 201, r.text
    doc = r.json()
    assert doc["mime"] == "application/pdf" and doc["tamano"] == len(PDF)

    en_disco = _archivo_en_disco(db, doc["id"]).read_bytes()
    assert b"%PDF" not in en_disco  # el archivo guardado está cifrado

    r = client.get(f"{A}/{alumno['id']}/documentos/{doc['id']}/archivo", headers=h_admin)
    assert r.status_code == 200 and r.content == PDF
    assert r.headers["content-type"] == "application/pdf" and "attachment" in r.headers["content-disposition"]
    acciones = {a.accion for a in db.scalars(select(Auditoria))}
    assert {"documento.subir", "documento.descargar"} <= acciones


def test_archivo_con_extension_falsa_se_rechaza(client, h_admin):
    alumno = crear_alumno(client, h_admin)
    r = _subir(client, h_admin, alumno["id"], contenido=b"MZ\x90\x00 ejecutable disfrazado", nombre="cedula.pdf")
    assert r.status_code == 422 and "PDF, JPG o PNG" in r.json()["detail"]


def test_archivo_vacio_se_rechaza(client, h_admin):
    assert _subir(client, h_admin, crear_alumno(client, h_admin)["id"], contenido=b"").status_code == 422


def test_tamano_maximo_es_configurable(client, h_admin, crear_usuario, auth_header):
    crear_usuario("root@club.com", "SUPERADMIN")
    client.patch("/api/v1/configuracion/documento_max_mb", json={"valor": 1}, headers=auth_header("root@club.com"))
    alumno = crear_alumno(client, h_admin)
    grande = PDF + b"0" * (1024 * 1024)
    r = _subir(client, h_admin, alumno["id"], contenido=grande)
    assert r.status_code == 422 and "1 MB" in r.json()["detail"]


def test_tipo_de_documento_invalido_se_rechaza(client, h_admin):
    assert _subir(client, h_admin, crear_alumno(client, h_admin)["id"], tipo="pasaporte_falso").status_code == 422


def test_miembro_ve_documentos_de_su_hijo_pero_no_sube_ni_ve_ajenos(client, h_admin, crear_usuario, auth_header):
    padre = crear_usuario("padre@club.com", "MIEMBRO")
    hijo = crear_menor(client, h_admin, acudiente=crear_acudiente(client, h_admin, usuario_id=str(padre.id)))
    ajeno = crear_alumno(client, h_admin, documento="4444444444")
    h = auth_header("padre@club.com")
    assert _subir(client, h, hijo["id"]).status_code == 403
    doc = _subir(client, h_admin, hijo["id"]).json()
    assert [d["id"] for d in client.get(f"{A}/{hijo['id']}/documentos", headers=h).json()] == [doc["id"]]
    assert client.get(f"{A}/{hijo['id']}/documentos/{doc['id']}/archivo", headers=h).content == PDF
    assert client.get(f"{A}/{ajeno['id']}/documentos", headers=h).status_code == 404


def test_entrenador_sube_y_ve_documentos_de_cualquier_alumno(client, h_admin, crear_usuario, auth_header):
    fem = crear_alumno(client, h_admin, rama="femenina")
    mas = crear_alumno(client, h_admin, documento="2222222222", rama="masculina")
    crear_usuario("coach@club.com", "ENTRENADOR")
    h = auth_header("coach@club.com")
    for alumno in (fem, mas):
        doc = _subir(client, h, alumno["id"])
        assert doc.status_code == 201
        assert client.get(f"{A}/{alumno['id']}/documentos/{doc.json()['id']}/archivo", headers=h).content == PDF


def test_eliminar_documento_borra_el_archivo_y_queda_auditado(client, h_admin, crear_usuario, auth_header, db):
    padre = crear_usuario("padre@club.com", "MIEMBRO")
    hijo = crear_menor(client, h_admin, acudiente=crear_acudiente(client, h_admin, usuario_id=str(padre.id)))
    doc = _subir(client, h_admin, hijo["id"]).json()
    ruta = _archivo_en_disco(db, doc["id"])
    # El acudiente no puede borrar; solo el staff con "alumnos.editar".
    url = f"{A}/{hijo['id']}/documentos/{doc['id']}"
    assert client.delete(url, headers=auth_header("padre@club.com")).status_code == 403
    assert client.delete(url, headers=h_admin).status_code == 204
    assert not ruta.exists()
    assert "documento.eliminar" in {a.accion for a in db.scalars(select(Auditoria))}


# ---------- Eliminar alumno (purga) ----------
def test_superadmin_elimina_un_alumno_con_toda_su_informacion(client, h_admin, crear_usuario, auth_header, db):
    from sqlalchemy import text

    crear_usuario("root@club.com", "SUPERADMIN")
    h_root = auth_header("root@club.com")
    alumno = crear_menor(client, h_admin)
    acudiente_id = alumno["acudientes"][0]["acudiente_id"]
    i = client.post("/api/v1/inscripciones", json={"alumno_id": alumno["id"]}, headers=h_admin).json()
    client.post(f"/api/v1/inscripciones/{i['id']}/pagos",
                json={"fecha_pago": i["fecha_inscripcion"], "monto": 40000}, headers=h_admin)
    doc = _subir(client, h_admin, alumno["id"]).json()
    archivo = _archivo_en_disco(db, doc["id"])
    assert archivo.exists()

    # Solo el SuperAdmin.
    assert client.delete(f"{A}/{alumno['id']}", headers=h_admin).status_code == 403
    assert client.delete(f"{A}/{alumno['id']}", headers=h_root).status_code == 204

    assert client.get(f"{A}/{alumno['id']}", headers=h_root).status_code == 404
    for tabla in ("alumnos", "inscripciones", "pagos_inscripcion", "documentos_alumno", "alumno_acudiente"):
        assert db.scalar(text(f"SELECT count(*) FROM {tabla}")) == 0, tabla  # noqa: S608
    assert not archivo.exists()
    # El acudiente se conserva (podría serlo de un hermano) y la auditoría solo guarda el código.
    assert client.get(f"/api/v1/acudientes/{acudiente_id}", headers=h_root).status_code == 200
    registro = db.execute(text("SELECT antes FROM auditoria WHERE accion = 'alumno.eliminar'")).scalar_one()
    assert registro["codigo"] == alumno["codigo"] and "nombres" not in registro and registro["inscripciones"] == 1


def test_fuera_de_la_purga_la_evidencia_sigue_protegida(client, h_admin, db):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    alumno = crear_alumno(client, h_admin)
    i = client.post("/api/v1/inscripciones", json={"alumno_id": alumno["id"]}, headers=h_admin).json()
    client.post(f"/api/v1/inscripciones/{i['id']}/pagos",
                json={"fecha_pago": i["fecha_inscripcion"], "monto": 1000}, headers=h_admin)
    with pytest.raises(DBAPIError, match="solo agregar"):
        db.execute(text("DELETE FROM pagos_inscripcion"))
    db.rollback()
    with pytest.raises(DBAPIError, match="solo agregar"):  # ni siquiera con la purga se borra la auditoría
        db.execute(text("SET LOCAL dragones.purga = 'on'"))
        db.execute(text("DELETE FROM auditoria"))
    db.rollback()
