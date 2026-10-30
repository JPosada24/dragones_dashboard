import json

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.core import cifrado
from app.models.alumnos import Alumno
from app.models.sistema import Auditoria
from tests.fabrica import AC, A, crear_acudiente, crear_alumno, crear_menor, datos_alumno, inscribir


@pytest.fixture
def h_admin(crear_usuario, auth_header):
    crear_usuario("adm@club.com", "ADMIN")
    return auth_header("adm@club.com")


# ---------- Alta y reglas de edad ----------
def test_admin_crea_alumno_mayor_sin_acudiente(client, h_admin, db):
    r = client.post(A, json=datos_alumno(anios=20), headers=h_admin)
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["documento"] == "****0002" and cuerpo["es_menor"] is False and cuerpo["acudientes"] == []
    acciones = [a.accion for a in db.scalars(select(Auditoria))]
    assert "alumno.crear" in acciones


def test_menor_sin_acudiente_se_rechaza(client, h_admin):
    r = client.post(A, json=datos_alumno(anios=12), headers=h_admin)
    assert r.status_code == 422
    assert "menor de edad" in r.json()["detail"] and "acudiente" in r.json()["detail"]


def test_menor_con_acudiente_se_crea_y_el_primero_es_principal(client, h_admin):
    alumno = crear_menor(client, h_admin)
    assert alumno["es_menor"] is True
    assert len(alumno["acudientes"]) == 1 and alumno["acudientes"][0]["principal"] is True


def test_edad_de_mayoria_es_configurable(client, crear_usuario, auth_header, h_admin):
    crear_usuario("root@club.com", "SUPERADMIN")
    h_root = auth_header("root@club.com")
    assert client.patch("/api/v1/configuracion/edad_mayoria", json={"valor": 21}, headers=h_root).status_code == 200
    # Con mayoría a los 21, alguien de 20 años ya necesita acudiente.
    assert client.post(A, json=datos_alumno(anios=20), headers=h_admin).status_code == 422


def test_no_se_puede_quitar_el_ultimo_acudiente_de_un_menor(client, h_admin):
    alumno = crear_menor(client, h_admin)
    acudiente_id = alumno["acudientes"][0]["acudiente_id"]
    r = client.delete(f"{A}/{alumno['id']}/acudientes/{acudiente_id}", headers=h_admin)
    assert r.status_code == 422 and "último acudiente" in r.json()["detail"]

    # Con un segundo acudiente sí se puede quitar uno, y el otro pasa a ser principal.
    otro = crear_acudiente(client, h_admin, documento="5555555555")
    r = client.post(f"{A}/{alumno['id']}/acudientes", json={"acudiente_id": otro["id"], "parentesco": "padre"},
                    headers=h_admin)
    assert r.status_code == 200
    r = client.delete(f"{A}/{alumno['id']}/acudientes/{acudiente_id}", headers=h_admin)
    assert r.status_code == 200
    assert [(a["acudiente_id"], a["principal"]) for a in r.json()["acudientes"]] == [(otro["id"], True)]


def test_un_mayor_puede_quedar_sin_acudiente(client, h_admin):
    acudiente = crear_acudiente(client, h_admin)
    alumno = crear_alumno(client, h_admin, acudientes=[{"acudiente_id": acudiente["id"], "parentesco": "madre"}])
    r = client.delete(f"{A}/{alumno['id']}/acudientes/{acudiente['id']}", headers=h_admin)
    assert r.status_code == 200 and r.json()["acudientes"] == []


def test_editar_fecha_para_volverlo_menor_sin_acudiente_se_rechaza(client, h_admin):
    alumno = crear_alumno(client, h_admin, anios=20)
    r = client.patch(f"{A}/{alumno['id']}", json={"fecha_nacimiento": "2018-05-05"}, headers=h_admin)
    assert r.status_code == 422


# ---------- Rama ----------
def test_rama_invalida_se_rechaza_en_api_y_en_base_de_datos(client, h_admin, db):
    assert client.post(A, json=datos_alumno(rama="mixta"), headers=h_admin).status_code == 422
    alumno = crear_alumno(client, h_admin)
    with pytest.raises(IntegrityError):
        db.execute(text("UPDATE alumnos SET rama = 'mixta' WHERE id = :id"), {"id": alumno["id"]})
    db.rollback()


# ---------- Documento de identidad cifrado ----------
def test_documento_cifrado_en_reposo(client, h_admin, db):
    alumno = crear_alumno(client, h_admin, documento="1.234.567.890")  # se normaliza a 1234567890
    fila = db.execute(
        text("SELECT documento_cifrado, documento_indice FROM alumnos WHERE id = :id"), {"id": alumno["id"]}
    ).one()
    assert b"1234567890" not in bytes(fila.documento_cifrado) and "1234567890" not in fila.documento_indice
    assert cifrado.descifrar(bytes(fila.documento_cifrado)) == "1234567890"
    assert alumno["documento"] == "****7890"


def test_documento_duplicado_aunque_se_escriba_distinto(client, h_admin):
    crear_alumno(client, h_admin, documento="1234567890")
    r = client.post(A, json=datos_alumno(documento="1.234.567.890"), headers=h_admin)
    assert r.status_code == 409


def test_documento_completo_solo_admin_y_queda_auditado(client, h_admin, crear_usuario, auth_header, db):
    alumno = crear_alumno(client, h_admin, documento="1234567890")
    r = client.get(f"{A}/{alumno['id']}/documento-identidad", headers=h_admin)
    assert r.status_code == 200 and r.json()["documento"] == "1234567890"

    crear_usuario("coach@club.com", "ENTRENADOR", rama="femenina")
    r = client.get(f"{A}/{alumno['id']}/documento-identidad", headers=auth_header("coach@club.com"))
    assert r.status_code == 403

    auditoria = list(db.scalars(select(Auditoria)))
    assert "alumno.ver_documento" in {a.accion for a in auditoria}
    # El número nunca aparece en claro en la bitácora.
    assert all("1234567890" not in json.dumps([a.antes, a.despues]) for a in auditoria)


def test_buscar_acudiente_por_documento_sin_descifrar(client, h_admin):
    crear_acudiente(client, h_admin, documento="1000000001")
    r = client.get(AC, params={"tipo_documento": "CC", "documento": "1.000.000.001"}, headers=h_admin)
    assert r.status_code == 200 and len(r.json()) == 1
    r = client.get(AC, params={"tipo_documento": "CC", "documento": "999999"}, headers=h_admin)
    assert r.json() == []


# ---------- Permisos y visibilidad ----------
def test_entrenador_solo_ve_su_rama(client, h_admin, crear_usuario, auth_header):
    fem = crear_alumno(client, h_admin, documento="1111111111", rama="femenina")
    mas = crear_alumno(client, h_admin, documento="2222222222", rama="masculina")
    crear_usuario("coach@club.com", "ENTRENADOR", rama="masculina")
    h = auth_header("coach@club.com")
    assert [a["id"] for a in client.get(A, headers=h).json()] == [mas["id"]]
    assert client.get(f"{A}/{fem['id']}", headers=h).status_code == 404


def test_entrenador_sin_rama_no_ve_alumnos(client, h_admin, crear_usuario, auth_header):
    crear_alumno(client, h_admin)
    crear_usuario("coach@club.com", "ENTRENADOR")
    assert client.get(A, headers=auth_header("coach@club.com")).json() == []


def test_superadmin_asigna_rama_al_entrenador(client, crear_usuario, auth_header):
    crear_usuario("root@club.com", "SUPERADMIN")
    coach = crear_usuario("coach@club.com", "ENTRENADOR")
    h = auth_header("root@club.com")
    r = client.patch(f"/api/v1/usuarios/{coach.id}", json={"rama": "femenina"}, headers=h)
    assert r.status_code == 200 and r.json()["rama"] == "femenina"
    assert client.patch(f"/api/v1/usuarios/{coach.id}", json={"rama": "mixta"}, headers=h).status_code == 422


def test_miembro_solo_ve_a_sus_hijos(client, h_admin, crear_usuario, auth_header):
    padre = crear_usuario("padre@club.com", "MIEMBRO")
    acudiente = crear_acudiente(client, h_admin, usuario_id=str(padre.id))
    hijo = crear_menor(client, h_admin, documento="3333333333", acudiente=acudiente)
    ajeno = crear_alumno(client, h_admin, documento="4444444444")
    h = auth_header("padre@club.com")
    assert [a["id"] for a in client.get(A, headers=h).json()] == [hijo["id"]]
    assert client.get(f"{A}/{ajeno['id']}", headers=h).status_code == 404


def test_alumno_mayor_con_cuenta_se_ve_a_si_mismo(client, h_admin, crear_usuario, auth_header):
    cuenta = crear_usuario("laura@club.com", "MIEMBRO")
    alumno = crear_alumno(client, h_admin, usuario_id=str(cuenta.id))
    crear_alumno(client, h_admin, documento="4444444444")
    assert [a["id"] for a in client.get(A, headers=auth_header("laura@club.com")).json()] == [alumno["id"]]


def test_miembro_no_crea_ni_edita_alumnos(client, h_admin, crear_usuario, auth_header):
    alumno = crear_alumno(client, h_admin)
    crear_usuario("m@club.com", "MIEMBRO")
    h = auth_header("m@club.com")
    assert client.post(A, json=datos_alumno(documento="7777777777"), headers=h).status_code == 403
    assert client.patch(f"{A}/{alumno['id']}", json={"nombres": "Otra"}, headers=h).status_code == 403
    assert client.post(AC, json={}, headers=h).status_code in (403, 422)


def test_entrenador_registra_y_edita_solo_alumnos_de_su_rama(client, h_admin, crear_usuario, auth_header):
    crear_usuario("coach@club.com", "ENTRENADOR", rama="femenina")
    h = auth_header("coach@club.com")
    acudiente = crear_acudiente(client, h)  # también registra acudientes
    propia = crear_menor(client, h, acudiente=acudiente)
    assert propia["rama"] == "femenina"

    r = client.post(A, json=datos_alumno(documento="7777777777", rama="masculina"), headers=h)
    assert r.status_code == 403 and "tu rama" in r.json()["detail"]
    # Tampoco puede "sacar" un alumno de su rama.
    assert client.patch(f"{A}/{propia['id']}", json={"rama": "masculina"}, headers=h).status_code == 403
    ajeno = crear_alumno(client, h_admin, documento="2222222222", rama="masculina")
    assert client.patch(f"{A}/{ajeno['id']}", json={"nombres": "Otro"}, headers=h).status_code == 404


def test_entrenador_sin_rama_no_registra_alumnos(client, crear_usuario, auth_header):
    crear_usuario("coach@club.com", "ENTRENADOR")
    r = client.post(A, json=datos_alumno(), headers=auth_header("coach@club.com"))
    assert r.status_code == 403 and "rama asignada" in r.json()["detail"]


def test_editar_alumno_queda_en_auditoria_con_antes_y_despues(client, h_admin, db):
    alumno = crear_alumno(client, h_admin)
    assert client.patch(f"{A}/{alumno['id']}", json={"rama": "masculina"}, headers=h_admin).status_code == 200
    fila = db.scalar(select(Auditoria).where(Auditoria.accion == "alumno.actualizar"))
    assert fila.antes["rama"] == "femenina" and fila.despues["rama"] == "masculina"
    assert fila.entidad_id == alumno["id"] and db.get(Alumno, fila.entidad_id) is not None


# ---------- Listado: búsqueda, filtros y estado de inscripción ----------
def test_buscar_por_documento_completo_y_filtrar_activos(client, h_admin):
    laura = crear_alumno(client, h_admin, documento="1234567890")
    crear_alumno(client, h_admin, documento="2222222222", nombres="Sara", apellidos="Ríos")

    def nombres(**params):
        r = client.get(A, params=params, headers=h_admin)
        assert r.status_code == 200, r.text
        return [a["nombres"] for a in r.json()]

    assert nombres(buscar="1.234.567.890") == ["Laura"]  # documento completo, con puntos
    assert nombres(buscar="4567") == []  # nunca por partes: no sirve para adivinar documentos
    assert nombres(buscar="Ríos") == ["Sara"]

    assert client.patch(f"{A}/{laura['id']}", json={"activo": False}, headers=h_admin).status_code == 200
    assert nombres(activo="true") == ["Sara"]
    assert nombres(activo="false") == ["Laura"]


def test_la_lista_trae_el_estado_de_la_inscripcion_del_anio(client, h_admin):
    inscrito = crear_alumno(client, h_admin)
    sin_inscripcion = crear_alumno(client, h_admin, documento="2222222222", nombres="Sara")
    assert inscribir(client, h_admin, inscrito["id"]).status_code == 201
    estados = {a["id"]: a["inscripcion_estado"] for a in client.get(A, headers=h_admin).json()}
    assert estados == {inscrito["id"]: "pendiente_pago", sin_inscripcion["id"]: None}
    detalle = client.get(f"{A}/{inscrito['id']}", headers=h_admin).json()
    assert detalle["inscripcion_estado"] == "pendiente_pago"
