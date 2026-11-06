"""Anuncio (flyer) de los torneos con inscripciones abiertas y paso a «Torneos realizados»."""
import io
import uuid
from datetime import timedelta

from PIL import Image
from sqlalchemy import select

from app.core.almacen import get_almacen
from app.models.sistema import Auditoria
from app.models.torneos import Torneo
from tests.fabrica import INICIO, T, ajustar_permisos, crear_torneo, en_hora

C = "/api/v1/club"
P = "/api/v1/publico"


def flyer(ancho=1080, alto=1350) -> bytes:
    imagen = Image.new("RGB", (ancho, alto), (242, 105, 30))
    exif = Image.Exif()
    exif[0x010F] = "Telefono de prueba"
    salida = io.BytesIO()
    imagen.save(salida, "JPEG", exif=exif)
    return salida.getvalue()


def subir(client, h, torneo_id, datos: bytes | None = None):
    return client.post(f"{T}/{torneo_id}/anuncio", files={"archivo": ("flyer.jpg", datos or flyer(), "image/jpeg")},
                       headers=h)


def torneo(client, h, **extra) -> dict:
    r = crear_torneo(client, h, **extra)
    assert r.status_code == 201, r.text
    return r.json()


def test_el_flyer_se_guarda_entero_sin_metadatos_y_reemplaza_al_anterior(client, h_admin, db):
    t = torneo(client, h_admin)
    assert t["anuncio"] is None and t["realizado_id"] is None
    r = subir(client, h_admin, t["id"], flyer(3000, 4000))
    assert r.status_code == 200, r.text
    d = r.json()
    assert len(d["anuncio"]) == 8 and (d["anuncio_ancho"], d["anuncio_alto"]) == (1440, 1920)
    grande = client.get(f"{T}/{t['id']}/anuncio?tam=grande", headers=h_admin)
    assert grande.status_code == 200 and "no-store" in grande.headers["cache-control"]
    with Image.open(io.BytesIO(grande.content)) as im:
        assert im.size == (1440, 1920) and not im.getexif()

    fila = db.get(Torneo, uuid.UUID(t["id"]))
    viejas = [fila.anuncio_clave, fila.anuncio_mini_clave]
    assert subir(client, h_admin, t["id"]).json()["anuncio"] != d["anuncio"]
    assert all(not get_almacen()._ruta(c).exists() for c in viejas)
    assert client.delete(f"{T}/{t['id']}/anuncio", headers=h_admin).json()["anuncio"] is None
    assert client.get(f"{T}/{t['id']}/anuncio", headers=h_admin).status_code == 404
    acciones = set(db.scalars(select(Auditoria.accion).where(Auditoria.entidad == "torneo")))
    assert {"torneo.anuncio", "torneo.anuncio_quitar"} <= acciones


def test_solo_quien_gestiona_torneos(client, h_admin, h_entrenador):
    t = torneo(client, h_admin)
    assert subir(client, h_entrenador, t["id"]).status_code == 403
    assert client.delete(f"{T}/{t['id']}/anuncio", headers=h_entrenador).status_code == 403
    assert client.get(f"{T}/{t['id']}/anuncio", headers=h_entrenador).status_code == 403
    assert subir(client, h_admin, t["id"], b"no es una imagen").status_code == 422


def test_el_sitio_muestra_el_flyer_solo_mientras_las_inscripciones_estan_abiertas(client, h_admin, reloj):
    t = torneo(client, h_admin)
    subir(client, h_admin, t["id"])
    url = f"{P}/torneos/{t['id']}/anuncio"
    assert client.get(url).status_code == 404  # sitio sin publicar
    client.patch(f"{C}/perfil", json={"publicado": True}, headers=h_admin)
    [abierto] = client.get(f"{P}/club").json()["torneos"]
    assert len(abierto["anuncio"]) == 8 and abierto["anuncio_alto"] == 1350 and "anuncio_clave" not in abierto
    r = client.get(f"{url}?tam=grande")
    assert r.status_code == 200 and "public" in r.headers["cache-control"]
    # Cerradas las inscripciones, el flyer deja de ser público.
    reloj(en_hora(INICIO - timedelta(days=4), 9))
    assert client.get(url).status_code == 404


def test_un_torneo_cancelado_no_expone_su_flyer(client, h_admin):
    t = torneo(client, h_admin)
    subir(client, h_admin, t["id"])
    client.patch(f"{C}/perfil", json={"publicado": True}, headers=h_admin)
    assert client.post(f"{T}/{t['id']}/cancelar", json={}, headers=h_admin).status_code == 200
    assert client.get(f"{P}/torneos/{t['id']}/anuncio").status_code == 404


def test_pasar_a_realizados_copia_los_datos_y_el_flyer_oculto(client, h_admin, reloj, db):
    t = torneo(client, h_admin, lugar="Coliseo Mayor")
    subir(client, h_admin, t["id"])
    url = f"{T}/{t['id']}/realizado"
    r = client.post(url, headers=h_admin)
    assert r.status_code == 422 and "aún no se ha jugado" in r.json()["detail"]

    reloj(en_hora(INICIO + timedelta(days=2), 9))
    r = client.post(url, headers=h_admin)
    assert r.status_code == 201, r.text
    hecho = r.json()
    assert (hecho["nombre"], hecho["fecha"], hecho["lugar"]) == ("Copa Dragones", INICIO.isoformat(), "Coliseo Mayor")
    assert hecho["publicado"] is False and hecho["anuncio_alto"] == 1350  # oculto hasta que tenga resultados
    assert client.get(f"{T}/{t['id']}", headers=h_admin).json()["realizado_id"] == hecho["id"]
    assert client.post(url, headers=h_admin).status_code == 422  # una sola vez

    # El flyer se copió: quitarlo del torneo no deja sin imagen a la ficha de realizados.
    client.delete(f"{T}/{t['id']}/anuncio", headers=h_admin)
    assert client.get(f"{C}/torneos-realizados/{hecho['id']}/anuncio", headers=h_admin).status_code == 200


def test_pasar_a_realizados_sin_flyer_y_no_si_se_cancelo(client, h_admin, reloj):
    sin_flyer = torneo(client, h_admin)
    cancelado = torneo(client, h_admin, nombre="Copa cancelada")
    client.post(f"{T}/{cancelado['id']}/cancelar", json={}, headers=h_admin)
    reloj(en_hora(INICIO, 9))
    r = client.post(f"{T}/{sin_flyer['id']}/realizado", headers=h_admin)
    assert r.status_code == 201 and r.json()["anuncio"] is None
    r = client.post(f"{T}/{cancelado['id']}/realizado", headers=h_admin)
    assert r.status_code == 422 and "cancelado" in r.json()["detail"]


def test_pasar_a_realizados_exige_tambien_editar_el_sitio(client, h_root, h_admin, h_entrenador, reloj):
    t = torneo(client, h_admin)
    reloj(en_hora(INICIO, 9))
    ajustar_permisos(client, h_root, h_entrenador, dar={"eventos.gestionar"})
    assert client.get(f"{T}/{t['id']}", headers=h_entrenador).status_code == 200  # gestiona torneos…
    assert client.post(f"{T}/{t['id']}/realizado", headers=h_entrenador).status_code == 403  # …pero no el sitio
