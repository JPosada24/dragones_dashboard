from app.core.config import get_settings
from tests.conftest import PASSWORD
from tests.fabrica import AC, PDF, A, crear_acudiente, crear_alumno, crear_menor


# ---------- Límite de logins fallidos por IP ----------
def test_muchos_fallos_desde_una_ip_bloquean_aunque_sean_cuentas_distintas(client, crear_usuario, login):
    crear_usuario("adm@club.com", "ADMIN")
    for n in range(get_settings().login_fallos_por_ip):
        assert login(f"intruso{n}@club.com", "ClaveFalsa12345").status_code == 401
    r = login("adm@club.com", PASSWORD)  # ni siquiera la clave correcta pasa mientras dure el bloqueo
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0


def test_los_logins_correctos_no_cuentan_para_el_limite(client, crear_usuario, login):
    crear_usuario("adm@club.com", "ADMIN")
    for _ in range(get_settings().login_fallos_por_ip + 5):
        assert login("adm@club.com", PASSWORD).status_code == 200


# ---------- Tamaño máximo de petición ----------
def test_peticion_demasiado_grande_se_rechaza_con_413(client, crear_usuario, auth_header):
    crear_usuario("adm@club.com", "ADMIN")
    h = auth_header("adm@club.com")
    alumno = crear_alumno(client, h)
    enorme = PDF + b"0" * (get_settings().max_cuerpo_mb * 1024 * 1024)
    r = client.post(
        f"{A}/{alumno['id']}/documentos", data={"tipo": "identidad"},
        files={"archivo": ("grande.pdf", enorme, "application/pdf")}, headers=h,
    )
    assert r.status_code == 413


def test_cuerpo_chunked_que_excede_el_limite_tambien_se_corta(client, crear_usuario, auth_header):
    crear_usuario("adm@club.com", "ADMIN")
    h = auth_header("adm@club.com")
    trozo = b"x" * (1024 * 1024)

    def generador():  # sin Content-Length: se cuenta mientras llega
        for _ in range(get_settings().max_cuerpo_mb + 1):
            yield trozo

    r = client.post(A, content=generador(), headers={**h, "Content-Type": "application/json"})
    assert r.status_code == 413


# ---------- Acudientes visibles para el Entrenador ----------
def test_la_familia_solo_ve_acudientes_de_sus_alumnos(client, crear_usuario, auth_header):
    crear_usuario("adm@club.com", "ADMIN")
    h_admin = auth_header("adm@club.com")
    ajeno = crear_acudiente(client, h_admin, documento="5000000001")
    crear_menor(client, h_admin, documento="6000000001", acudiente=ajeno, rama="masculina")
    crear_usuario("coach@club.com", "ENTRENADOR")
    h = auth_header("coach@club.com")
    # El entrenador (general) ve y edita a todos los acudientes.
    assert client.get(f"{AC}/{ajeno['id']}", headers=h).status_code == 200
    # La familia no puede consultar acudientes.
    crear_usuario("m@club.com", "MIEMBRO")
    assert client.get(AC, headers=auth_header("m@club.com")).status_code == 403


def test_entrenador_encuentra_por_documento_exacto_al_acudiente_de_un_hermano(client, crear_usuario, auth_header):
    crear_usuario("adm@club.com", "ADMIN")
    h_admin = auth_header("adm@club.com")
    madre = crear_acudiente(client, h_admin, documento="5000000001")
    crear_menor(client, h_admin, documento="6000000001", acudiente=madre, rama="masculina")
    crear_usuario("coach@club.com", "ENTRENADOR")
    h = auth_header("coach@club.com")

    r = client.get(AC, params={"tipo_documento": "CC", "documento": "5000000001"}, headers=h)
    assert [a["id"] for a in r.json()] == [madre["id"]]
    # Con eso la vincula a la hermana de su rama, sin duplicar el acudiente.
    hermana = crear_alumno(
        client, h, documento="6000000002", anios=10, acudientes=[{"acudiente_id": madre["id"], "parentesco": "madre"}]
    )
    assert hermana["acudientes"][0]["acudiente_id"] == madre["id"]
