"""Rotación de la clave de cifrado (MultiFernet) y de la clave de los tokens, sin perder datos ni sesiones."""
import os

import jwt
import pytest
from cryptography.fernet import Fernet

from app.core import cifrado
from app.core.almacen import get_almacen
from app.core.config import get_settings
from app.core.security import ALGORITMO, crear_access_token, decodificar_access_token
from app.scripts.rotar_clave import rotar
from tests.fabrica import PDF, A, crear_alumno


@pytest.fixture
def usar_claves(monkeypatch):
    """Cambia DATA_ENCRYPTION_KEY / SECRET_KEY durante la prueba y deja todo como estaba al final."""

    def _usar(**variables: str) -> None:
        for nombre, valor in variables.items():
            monkeypatch.setenv(nombre, valor)
        get_settings.cache_clear()
        cifrado.reiniciar_claves()

    yield _usar
    monkeypatch.undo()
    get_settings.cache_clear()
    cifrado.reiniciar_claves()


def test_rotar_la_clave_de_cifrado_conserva_documentos_busquedas_y_archivos(client, h_admin, db, usar_claves):
    vieja = os.environ["DATA_ENCRYPTION_KEY"]
    alumno = crear_alumno(client, h_admin)
    archivo = client.post(f"{A}/{alumno['id']}/documentos", data={"tipo": "identidad"},
                          files={"archivo": ("ti.pdf", PDF, "application/pdf")}, headers=h_admin).json()

    nueva = Fernet.generate_key().decode()
    usar_claves(DATA_ENCRYPTION_KEY=f"{nueva},{vieja}")
    assert rotar(db, get_almacen()) == {"documentos_identidad": 1, "archivos": 1}
    db.commit()

    usar_claves(DATA_ENCRYPTION_KEY=nueva)  # la vieja ya no está: todo debe seguir legible
    r = client.get(f"{A}/{alumno['id']}/documento-identidad", headers=h_admin)
    assert r.json()["documento"] == "1000000002"
    encontrados = client.get(A, params={"buscar": "1000000002"}, headers=h_admin).json()
    assert [a["id"] for a in encontrados] == [alumno["id"]]  # el índice ciego se recalculó
    descarga = client.get(f"{A}/{alumno['id']}/documentos/{archivo['id']}/archivo", headers=h_admin)
    assert descarga.status_code == 200 and descarga.content == PDF


def test_varias_claves_invalidas_se_rechazan(usar_claves):
    with pytest.raises(ValueError, match="DATA_ENCRYPTION_KEY"):
        usar_claves(DATA_ENCRYPTION_KEY=f"{Fernet.generate_key().decode()},no-es-una-clave")
        get_settings()


def test_rotar_la_clave_de_los_tokens_no_cierra_las_sesiones(usar_claves):
    import uuid

    token, _ = crear_access_token(uuid.uuid4(), "ADMIN", 0)
    vieja = get_settings().secret_key
    usar_claves(SECRET_KEY="otra-clave-nueva-de-mas-de-treinta-y-dos-caracteres", SECRET_KEY_ANTERIOR=vieja)
    assert decodificar_access_token(token)["rol"] == "ADMIN"  # firmado con la anterior: sigue valiendo
    nuevo, _ = crear_access_token(uuid.uuid4(), "ADMIN", 0)
    assert jwt.get_unverified_header(nuevo)["alg"] == ALGORITMO

    usar_claves(SECRET_KEY_ANTERIOR="")  # terminó la rotación
    with pytest.raises(jwt.InvalidSignatureError):
        decodificar_access_token(token)
    assert decodificar_access_token(nuevo)["rol"] == "ADMIN"
