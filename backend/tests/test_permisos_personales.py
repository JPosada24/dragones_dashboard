"""Permisos por persona: el SuperAdmin da o quita permisos a un Admin o Entrenador además de su rol."""
from sqlalchemy import select

from app.models.sistema import Auditoria
from tests.fabrica import U, ajustar_permisos


def _id(client, h) -> str:
    return client.get("/api/v1/auth/me", headers=h).json()["id"]


def test_dar_un_permiso_a_un_entrenador_aplica_sin_volver_a_entrar(client, h_root, h_entrenador):
    assert client.get("/api/v1/reportes/ingresos", headers=h_entrenador).status_code == 403
    p = ajustar_permisos(client, h_root, h_entrenador, dar={"reportes.ver"})
    assert p["concedidos"] == ["reportes.ver"] and p["quitados"] == []
    assert "reportes.ver" in p["efectivos"] and "reportes.ver" not in p["de_rol"]
    # Mismo token: los permisos se leen en cada petición.
    assert client.get("/api/v1/reportes/ingresos", headers=h_entrenador).status_code == 200
    assert "reportes.ver" in client.get("/api/v1/auth/me", headers=h_entrenador).json()["permisos"]


def test_quitar_un_permiso_del_rol_a_un_admin(client, h_root, h_admin):
    assert client.get("/api/v1/reportes/ingresos", headers=h_admin).status_code == 200
    p = ajustar_permisos(client, h_root, h_admin, quitar={"reportes.ver"})
    assert p["quitados"] == ["reportes.ver"] and "reportes.ver" not in p["efectivos"]
    assert client.get("/api/v1/reportes/ingresos", headers=h_admin).status_code == 403
    # La lista de cuentas lo marca como personalizado.
    fila = next(u for u in client.get(U, headers=h_root).json() if u["email"] == "adm@club.com")
    assert fila["permisos_personalizados"] is True


def test_volver_a_los_del_rol_borra_los_ajustes(client, h_root, h_admin):
    ajustar_permisos(client, h_root, h_admin, quitar={"reportes.ver"})
    de_rol = client.get(f"{U}/{_id(client, h_admin)}/permisos", headers=h_root).json()["de_rol"]
    r = client.put(f"{U}/{_id(client, h_admin)}/permisos", json={"permisos": de_rol}, headers=h_root).json()
    assert r["concedidos"] == r["quitados"] == [] and r["efectivos"] == de_rol


def test_cambiar_el_rol_reinicia_los_permisos_personales(client, h_root, h_entrenador):
    ajustar_permisos(client, h_root, h_entrenador, dar={"reportes.ver"})
    uid = _id(client, h_entrenador)
    assert client.patch(f"{U}/{uid}", json={"rol": "ADMIN"}, headers=h_root).status_code == 200
    p = client.get(f"{U}/{uid}/permisos", headers=h_root).json()
    assert p["rol"] == "ADMIN" and p["concedidos"] == p["quitados"] == []


def test_administrar_cuentas_no_se_le_da_a_nadie(client, h_root, h_admin):
    uid = _id(client, h_admin)
    for vetado in ("usuarios.gestionar", "usuarios.eliminar", "alumnos.ver_propios"):
        r = client.put(f"{U}/{uid}/permisos", json={"permisos": [vetado]}, headers=h_root)
        assert r.status_code == 422, vetado
    r = client.put(f"{U}/{uid}/permisos", json={"permisos": ["no.existe"]}, headers=h_root)
    assert r.status_code == 422
    assert client.get(U, headers=h_admin).status_code == 403  # el Admin no administra cuentas


def test_solo_el_superadmin_ajusta_y_no_a_si_mismo_ni_a_familias(client, h_root, h_admin, crear_usuario):
    uid_admin = _id(client, h_admin)
    # El Admin no puede ajustar permisos de nadie (ni verlos).
    assert client.get(f"{U}/{uid_admin}/permisos", headers=h_admin).status_code == 403
    assert client.put(f"{U}/{uid_admin}/permisos", json={"permisos": []}, headers=h_admin).status_code == 403
    # Al SuperAdmin (él mismo) y a una cuenta de familia no se les ajusta.
    assert client.put(f"{U}/{_id(client, h_root)}/permisos", json={"permisos": []}, headers=h_root).status_code == 422
    miembro = crear_usuario("papa@club.com", "MIEMBRO")
    r = client.put(f"{U}/{miembro.id}/permisos", json={"permisos": ["alumnos.ver_todos"]}, headers=h_root)
    assert r.status_code == 422
    assert client.get(f"{U}/{miembro.id}/permisos", headers=h_root).json()["personalizable"] is False


def test_el_ajuste_queda_en_la_auditoria(client, h_root, h_entrenador, db):
    ajustar_permisos(client, h_root, h_entrenador, dar={"reportes.ver"}, quitar={"asistencia.marcar_grupo"})
    fila = db.scalar(select(Auditoria).where(Auditoria.accion == "usuario.permisos"))
    assert fila.despues == {"concedidos": ["reportes.ver"], "quitados": ["asistencia.marcar_grupo"]}
    assert fila.antes == {"concedidos": [], "quitados": []}
