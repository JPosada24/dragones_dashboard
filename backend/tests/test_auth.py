import jwt
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError

from app.core.config import get_settings
from app.models.acceso import SesionRefresh, Usuario
from app.models.sistema import Auditoria
from tests.conftest import PASSWORD


def test_salud(client):
    r = client.get("/api/v1/salud")
    assert r.status_code == 200 and r.json() == {"estado": "ok"}


def test_login_correcto_devuelve_token_cookie_y_permisos(client, crear_usuario, login):
    crear_usuario("admin@club.com", "ADMIN")
    r = login("admin@club.com")
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["token_type"] == "bearer" and cuerpo["expires_in"] == 900
    assert cuerpo["usuario"]["rol"] == "ADMIN"
    assert "pagos.registrar" in cuerpo["usuario"]["permisos"]
    assert "usuarios.gestionar" not in cuerpo["usuario"]["permisos"]
    cookie = r.headers["set-cookie"].lower()
    assert "refresh_token=" in cookie and "httponly" in cookie and "samesite=strict" in cookie


def test_login_normaliza_el_correo(client, crear_usuario, login):
    crear_usuario("admin@club.com", "ADMIN")
    assert login("  ADMIN@Club.com ").status_code == 200


def test_login_incorrecto_da_mensaje_generico(client, crear_usuario, login):
    crear_usuario("admin@club.com", "ADMIN")
    r1 = login("admin@club.com", "OtraClave123456")
    r2 = login("noexiste@club.com", "OtraClave123456")
    assert r1.status_code == r2.status_code == 401
    assert r1.json() == r2.json()


def test_bloqueo_tras_intentos_fallidos(client, crear_usuario, login):
    crear_usuario("admin@club.com", "ADMIN")
    for _ in range(get_settings().max_intentos_login):
        assert login("admin@club.com", "MalaClave123456").status_code == 401
    # Aunque ahora la clave sea correcta, la cuenta está bloqueada temporalmente.
    assert login("admin@club.com").status_code == 401


def test_usuario_inactivo_no_entra(client, crear_usuario, login, db):
    u = crear_usuario("admin@club.com", "ADMIN")
    u.activo = False
    db.commit()
    assert login("admin@club.com").status_code == 401


def test_me_requiere_token(client, auth_header, crear_usuario):
    assert client.get("/api/v1/auth/me").status_code == 401
    crear_usuario("m@club.com", "MIEMBRO")
    r = client.get("/api/v1/auth/me", headers=auth_header("m@club.com"))
    assert r.status_code == 200 and r.json()["email"] == "m@club.com"


def test_token_manipulado_o_de_otro_secreto_se_rechaza(client, crear_usuario):
    u = crear_usuario("m@club.com", "MIEMBRO")
    falso = jwt.encode({"sub": str(u.id), "tipo": "access", "iat": 1, "exp": 9999999999}, "otro-secreto-" * 4, "HS256")
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {falso}"})
    assert r.status_code == 401


def test_refresh_rota_el_token(client, crear_usuario, login):
    crear_usuario("m@club.com", "MIEMBRO")
    login("m@club.com")
    viejo = client.cookies.get("refresh_token")
    r = client.post("/api/v1/auth/refresh")
    assert r.status_code == 200 and r.json()["access_token"]
    nuevo = client.cookies.get("refresh_token")
    assert nuevo and nuevo != viejo


def test_reutilizar_un_refresh_ya_usado_revoca_toda_la_familia(client, crear_usuario, login, db):
    crear_usuario("m@club.com", "MIEMBRO")
    login("m@club.com")
    viejo = client.cookies.get("refresh_token")
    assert client.post("/api/v1/auth/refresh").status_code == 200  # rota: "viejo" queda revocado

    client.cookies.clear()
    client.cookies.set("refresh_token", viejo)
    assert client.post("/api/v1/auth/refresh").status_code == 401  # reuso detectado

    activas = db.scalars(select(SesionRefresh).where(SesionRefresh.revocado_en.is_(None))).all()
    assert activas == []  # la familia entera quedó revocada
    acciones = {a.accion for a in db.scalars(select(Auditoria))}
    assert "auth.refresh_reutilizado" in acciones


def test_logout_revoca_la_sesion(client, crear_usuario, login):
    crear_usuario("m@club.com", "MIEMBRO")
    login("m@club.com")
    token = client.cookies.get("refresh_token")
    assert client.post("/api/v1/auth/logout").status_code == 204
    client.cookies.set("refresh_token", token)
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_refresh_sin_cookie(client):
    assert client.post("/api/v1/auth/refresh").status_code == 401


def test_contrasena_se_guarda_con_argon2(crear_usuario, db):
    crear_usuario("m@club.com", "MIEMBRO")
    u = db.scalar(select(Usuario).where(Usuario.email == "m@club.com"))
    assert u.password_hash.startswith("$argon2id$") and PASSWORD not in u.password_hash


def test_la_auditoria_no_se_puede_editar_ni_borrar(db):
    db.add(Auditoria(accion="prueba", entidad="x"))
    db.commit()
    for sentencia in ("UPDATE auditoria SET accion = 'otra'", "DELETE FROM auditoria"):
        with pytest.raises(DBAPIError, match="solo agregar"):
            db.execute(text(sentencia))
        db.rollback()
    assert db.scalar(select(func.count()).select_from(Auditoria)) == 1


def test_el_login_deja_rastro_en_auditoria(client, crear_usuario, login, db):
    crear_usuario("m@club.com", "MIEMBRO")
    login("m@club.com", "MalaClave123456")
    login("m@club.com")
    acciones = [a.accion for a in db.scalars(select(Auditoria).order_by(Auditoria.id))]
    assert "auth.login_fallido" in acciones and "auth.login" in acciones
