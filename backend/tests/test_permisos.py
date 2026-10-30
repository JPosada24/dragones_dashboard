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


# ---------- Cuentas: vínculo de Miembros y contraseña ----------
def test_superadmin_crea_cuenta_de_miembro_vinculada_a_un_acudiente(client, crear_usuario, auth_header, login):
    from tests.fabrica import crear_alumno, crear_menor

    crear_usuario("root@club.com", "SUPERADMIN")
    h = auth_header("root@club.com")
    hija = crear_menor(client, h)
    acudiente_id = hija["acudientes"][0]["acudiente_id"]
    cuenta = {"email": "marta@club.com", "nombre": "Marta Gómez", "password": PASSWORD, "rol": "MIEMBRO"}

    # Un menor no tiene cuenta propia.
    r = client.post("/api/v1/usuarios", json={**cuenta, "vincular_alumno_id": hija["id"]}, headers=h)
    assert r.status_code == 422 and "acudiente" in r.json()["detail"]
    # Solo los Miembros se vinculan.
    r = client.post("/api/v1/usuarios", json={**cuenta, "rol": "ADMIN", "vincular_acudiente_id": acudiente_id},
                    headers=h)
    assert r.status_code == 422

    r = client.post("/api/v1/usuarios", json={**cuenta, "vincular_acudiente_id": acudiente_id}, headers=h)
    assert r.status_code == 201, r.text
    # Con la cuenta nueva, Marta ve a su hija.
    token = login("marta@club.com").json()["access_token"]
    alumnos = client.get("/api/v1/alumnos", headers={"Authorization": f"Bearer {token}"}).json()
    assert [a["id"] for a in alumnos] == [hija["id"]]
    lista = {u["email"]: u["vinculado_a"] for u in client.get("/api/v1/usuarios", headers=h).json()}
    assert lista["marta@club.com"].startswith("Acudiente de " + hija["codigo"])
    # Ya tiene cuenta: no se vincula otra.
    otra = {**cuenta, "email": "otra@club.com", "vincular_acudiente_id": acudiente_id}
    r = client.post("/api/v1/usuarios", json=otra, headers=h)
    assert r.status_code == 409

    mayor = crear_alumno(client, h, documento="1000000099")
    r = client.post("/api/v1/usuarios", json={**cuenta, "email": "laura@club.com", "vincular_alumno_id": mayor["id"]},
                    headers=h)
    assert r.status_code == 201


def test_superadmin_restablece_la_contrasena_y_cierra_las_sesiones(client, crear_usuario, auth_header, login):
    crear_usuario("root@club.com", "SUPERADMIN")
    usuario = crear_usuario("coach@club.com", "ENTRENADOR")
    h_coach = auth_header("coach@club.com")
    h_root = auth_header("root@club.com")
    nueva = "OtraClaveSegura456"
    assert client.patch(f"/api/v1/usuarios/{usuario.id}", json={"password": "123"}, headers=h_root).status_code == 422
    r = client.patch(f"/api/v1/usuarios/{usuario.id}", json={"password": nueva}, headers=h_root)
    assert r.status_code == 200
    assert client.get("/api/v1/auth/me", headers=h_coach).status_code == 401
    assert login("coach@club.com").status_code == 401
    assert login("coach@club.com", nueva).status_code == 200
