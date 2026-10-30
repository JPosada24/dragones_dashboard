from tests.conftest import PASSWORD

NUEVO = {"email": "nuevo@club.com", "nombre": "Nuevo Usuario", "password": PASSWORD, "rol": "ENTRENADOR"}


def test_sin_token_no_hay_acceso(client):
    assert client.get("/api/v1/usuarios").status_code == 401
    assert client.get("/api/v1/configuracion").status_code == 401


def test_superadmin_crea_usuarios(client, crear_usuario, auth_header):
    crear_usuario("root@club.com", "SUPERADMIN")
    r = client.post("/api/v1/usuarios", json=NUEVO, headers=auth_header("root@club.com"))
    assert r.status_code == 201
    assert r.json()["rol"] == "ENTRENADOR" and "password" not in r.json()


def test_admin_no_puede_gestionar_usuarios(client, crear_usuario, auth_header):
    crear_usuario("adm@club.com", "ADMIN")
    h = auth_header("adm@club.com")
    assert client.post("/api/v1/usuarios", json=NUEVO, headers=h).status_code == 403
    assert client.get("/api/v1/usuarios", headers=h).status_code == 403


def test_entrenador_y_miembro_no_gestionan_usuarios(client, crear_usuario, auth_header):
    for rol in ("ENTRENADOR", "MIEMBRO"):
        crear_usuario(f"{rol.lower()}@club.com", rol)
        h = auth_header(f"{rol.lower()}@club.com")
        assert client.post("/api/v1/usuarios", json=NUEVO, headers=h).status_code == 403


def test_correo_duplicado_da_409(client, crear_usuario, auth_header):
    crear_usuario("root@club.com", "SUPERADMIN")
    h = auth_header("root@club.com")
    assert client.post("/api/v1/usuarios", json=NUEVO, headers=h).status_code == 201
    assert client.post("/api/v1/usuarios", json=NUEVO, headers=h).status_code == 409


def test_contrasena_debil_se_rechaza(client, crear_usuario, auth_header):
    crear_usuario("root@club.com", "SUPERADMIN")
    h = auth_header("root@club.com")
    r = client.post("/api/v1/usuarios", json={**NUEVO, "password": "corta"}, headers=h)
    assert r.status_code == 422


def test_rol_inexistente_da_422(client, crear_usuario, auth_header):
    crear_usuario("root@club.com", "SUPERADMIN")
    r = client.post("/api/v1/usuarios", json={**NUEVO, "rol": "DIOS"}, headers=auth_header("root@club.com"))
    assert r.status_code == 422


def test_superadmin_no_puede_desactivarse_a_si_mismo(client, crear_usuario, auth_header):
    u = crear_usuario("root@club.com", "SUPERADMIN")
    r = client.patch(f"/api/v1/usuarios/{u.id}", json={"activo": False}, headers=auth_header("root@club.com"))
    assert r.status_code == 400


def test_desactivar_usuario_cierra_sus_sesiones(client, crear_usuario, auth_header, login):
    crear_usuario("root@club.com", "SUPERADMIN")
    miembro = crear_usuario("m@club.com", "MIEMBRO")
    h_miembro = auth_header("m@club.com")
    h_root = auth_header("root@club.com")
    r = client.patch(f"/api/v1/usuarios/{miembro.id}", json={"activo": False}, headers=h_root)
    assert r.status_code == 200 and r.json()["activo"] is False
    assert client.get("/api/v1/auth/me", headers=h_miembro).status_code == 401
    assert login("m@club.com").status_code == 401


def test_configuracion_lectura_y_edicion(client, crear_usuario, auth_header):
    crear_usuario("root@club.com", "SUPERADMIN")
    crear_usuario("adm@club.com", "ADMIN")
    h_root, h_adm = auth_header("root@club.com"), auth_header("adm@club.com")

    r = client.get("/api/v1/configuracion", headers=h_adm)  # el Admin puede ver
    assert r.status_code == 200
    valores = {c["clave"]: c["valor"] for c in r.json()}
    assert valores["multa_inasistencia"] == 2000 and valores["meses_mora_expulsion"] == 3
    assert valores["puestos_por_talonario"] == 20 and valores["precio_puesto"] == 2000

    # El Admin NO puede cambiar parámetros críticos
    r = client.patch("/api/v1/configuracion/multa_inasistencia", json={"valor": 5000}, headers=h_adm)
    assert r.status_code == 403
    # El SuperAdmin sí
    r = client.patch("/api/v1/configuracion/multa_inasistencia", json={"valor": 5000}, headers=h_root)
    assert r.status_code == 200 and r.json()["valor"] == 5000


def test_configuracion_valida_tipos(client, crear_usuario, auth_header):
    crear_usuario("root@club.com", "SUPERADMIN")
    h = auth_header("root@club.com")
    r = client.patch("/api/v1/configuracion/multa_inasistencia", json={"valor": "mucho"}, headers=h)
    assert r.status_code == 422
    assert client.patch("/api/v1/configuracion/multa_inasistencia", json={"valor": -1}, headers=h).status_code == 422
    assert client.patch("/api/v1/configuracion/expulsion_automatica", json={"valor": 1}, headers=h).status_code == 422
    assert client.patch("/api/v1/configuracion/no_existe", json={"valor": 1}, headers=h).status_code == 422
    r = client.patch("/api/v1/configuracion/hora_cierre_asistencia", json={"valor": "25:99"}, headers=h)
    assert r.status_code == 422
