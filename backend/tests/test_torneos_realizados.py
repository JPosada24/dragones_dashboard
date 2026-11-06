"""Torneos realizados: sección del sitio con los torneos ya jugados y su anuncio (afiche)."""
import io
import uuid

from PIL import Image
from sqlalchemy import select

from app.core.almacen import get_almacen
from app.models.club import TorneoRealizado
from app.models.sistema import Auditoria

C = "/api/v1/club"
R = f"{C}/torneos-realizados"
P = "/api/v1/publico"


def afiche(ancho=1080, alto=1350) -> bytes:
    """Afiche vertical (4:5, como los de Instagram) con metadatos EXIF, para comprobar que se quitan."""
    imagen = Image.new("RGB", (ancho, alto), (242, 105, 30))
    exif = Image.Exif()
    exif[0x010F] = "Telefono de prueba"
    salida = io.BytesIO()
    imagen.save(salida, "JPEG", exif=exif)
    return salida.getvalue()


def publicar_sitio(client, h):
    assert client.patch(f"{C}/perfil", json={"publicado": True}, headers=h).status_code == 200


def crear(client, h, **datos):
    cuerpo = {"nombre": "Copa Dragones 2025", "fecha": "2025-08-16", **datos}
    r = client.post(R, json=cuerpo, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def subir_anuncio(client, h, torneo_id, datos: bytes | None = None):
    return client.post(f"{R}/{torneo_id}/anuncio", files={"archivo": ("afiche.jpg", datos or afiche(), "image/jpeg")},
                       headers=h)


def test_solo_quien_edita_el_club(client, h_admin, h_entrenador):
    t = crear(client, h_admin)
    assert client.get(R).status_code == 401
    assert client.get(R, headers=h_entrenador).status_code == 403
    assert client.post(R, json={"nombre": "Otro", "fecha": "2025-01-01"}, headers=h_entrenador).status_code == 403
    assert client.patch(f"{R}/{t['id']}", json={"nombre": "X"}, headers=h_entrenador).status_code == 403
    assert client.delete(f"{R}/{t['id']}", headers=h_entrenador).status_code == 403
    assert subir_anuncio(client, h_entrenador, t["id"]).status_code == 403
    assert client.get(f"{R}/{t['id']}/anuncio", headers=h_entrenador).status_code == 403


def test_crear_editar_y_listar_del_mas_reciente_al_mas_antiguo(client, h_admin):
    crear(client, h_admin, nombre="Copa 2024", fecha="2024-05-04")
    t = crear(client, h_admin, lugar="Coliseo Mayor", resumen="Campeón: Club Halcones.")
    assert t["publicado"] is True and t["anuncio"] is None and t["album_id"] is None
    assert [x["nombre"] for x in client.get(R, headers=h_admin).json()] == ["Copa Dragones 2025", "Copa 2024"]
    # Lugar y resumen se quitan enviándolos vacíos; lo no enviado no cambia.
    r = client.patch(f"{R}/{t['id']}", json={"lugar": "", "resumen": None}, headers=h_admin)
    assert r.status_code == 200
    assert r.json()["lugar"] is None and r.json()["resumen"] is None and r.json()["nombre"] == "Copa Dragones 2025"


def test_entrada_validada(client, h_admin):
    assert client.post(R, json={"nombre": "Copa"}, headers=h_admin).status_code == 422  # sin fecha
    assert client.post(R, json={"nombre": "Copa", "fecha": "2025-01-01", "extra": 1},
                       headers=h_admin).status_code == 422
    assert client.post(R, json={"nombre": "Copa", "fecha": "2025-01-01", "resumen": "x" * 601},
                       headers=h_admin).status_code == 422
    r = client.post(R, json={"nombre": "Copa", "fecha": "2025-01-01", "album_id": str(uuid.uuid4())}, headers=h_admin)
    assert r.status_code == 422 and "álbum" in r.json()["detail"]
    assert client.patch(f"{R}/{uuid.uuid4()}", json={"nombre": "Copa"}, headers=h_admin).status_code == 404


def test_anuncio_entero_sin_metadatos_y_se_reemplaza_borrando_el_anterior(client, h_admin, db):
    t = crear(client, h_admin)
    r = subir_anuncio(client, h_admin, t["id"], afiche(3000, 4000))
    assert r.status_code == 200, r.text
    d = r.json()
    assert len(d["anuncio"]) == 8 and (d["anuncio_ancho"], d["anuncio_alto"]) == (1440, 1920)  # sin recortar
    grande = client.get(f"{R}/{t['id']}/anuncio?tam=grande", headers=h_admin)
    assert grande.status_code == 200 and "no-store" in grande.headers["cache-control"]
    with Image.open(io.BytesIO(grande.content)) as im:
        assert im.size == (1440, 1920) and not im.getexif()
    with Image.open(io.BytesIO(client.get(f"{R}/{t['id']}/anuncio", headers=h_admin).content)) as im:
        assert max(im.size) == 720

    fila = db.scalar(select(TorneoRealizado).where(TorneoRealizado.id == uuid.UUID(t["id"])))
    viejas = [fila.anuncio_clave, fila.anuncio_mini_clave]
    almacen = get_almacen()
    nuevo = subir_anuncio(client, h_admin, t["id"]).json()
    assert nuevo["anuncio"] != d["anuncio"]
    assert all(not almacen._ruta(c).exists() for c in viejas)  # el anterior no queda huérfano

    sin = client.delete(f"{R}/{t['id']}/anuncio", headers=h_admin).json()
    assert sin["anuncio"] is None and sin["anuncio_ancho"] is None
    assert client.get(f"{R}/{t['id']}/anuncio", headers=h_admin).status_code == 404


def test_un_archivo_que_no_es_imagen_se_rechaza(client, h_admin):
    t = crear(client, h_admin)
    r = subir_anuncio(client, h_admin, t["id"], b"%PDF-1.4 no es una imagen")
    assert r.status_code == 422


def test_en_el_sitio_solo_lo_publicado_y_el_album_solo_si_se_ve(client, h_admin):
    alb = client.post(f"{C}/albumes", json={"nombre": "Fotos Copa", "publicado": True}, headers=h_admin).json()
    t = crear(client, h_admin, album_id=alb["id"])
    oculto = crear(client, h_admin, nombre="Copa oculta", publicado=False)
    subir_anuncio(client, h_admin, t["id"])
    subir_anuncio(client, h_admin, oculto["id"])

    assert client.get(f"{P}/torneos-realizados/{t['id']}/anuncio").status_code == 404  # sitio sin publicar
    publicar_sitio(client, h_admin)
    [publico] = client.get(f"{P}/club").json()["torneos_realizados"]
    assert publico["nombre"] == "Copa Dragones 2025" and "anuncio_clave" not in publico
    assert publico["album_id"] is None  # el álbum aún no tiene fotos: no se ve en el sitio

    foto = Image.new("RGB", (800, 600))
    datos = io.BytesIO()
    foto.save(datos, "JPEG")
    client.post(f"{C}/albumes/{alb['id']}/fotos", data={"autorizacion": "true"},
                files={"archivo": ("f.jpg", datos.getvalue(), "image/jpeg")}, headers=h_admin)
    [publico] = client.get(f"{P}/club").json()["torneos_realizados"]
    assert publico["album_id"] == alb["id"]

    r = client.get(f"{P}/torneos-realizados/{t['id']}/anuncio?tam=grande")
    assert r.status_code == 200 and "public" in r.headers["cache-control"]
    assert client.get(f"{P}/torneos-realizados/{oculto['id']}/anuncio").status_code == 404
    assert client.get(f"{P}/torneos-realizados/{t['id']}/anuncio?tam=otro").status_code == 422


def test_borrar_el_album_quita_el_enlace_y_borrar_el_torneo_borra_su_anuncio(client, h_admin, db):
    alb = client.post(f"{C}/albumes", json={"nombre": "Fotos"}, headers=h_admin).json()
    t = crear(client, h_admin, album_id=alb["id"])
    assert client.delete(f"{C}/albumes/{alb['id']}", headers=h_admin).status_code == 204
    assert client.get(R, headers=h_admin).json()[0]["album_id"] is None

    subir_anuncio(client, h_admin, t["id"])
    fila = db.scalar(select(TorneoRealizado).where(TorneoRealizado.id == uuid.UUID(t["id"])))
    claves = [fila.anuncio_clave, fila.anuncio_mini_clave]
    assert client.delete(f"{R}/{t['id']}", headers=h_admin).status_code == 204
    assert client.get(R, headers=h_admin).json() == []
    assert all(not get_almacen()._ruta(c).exists() for c in claves)


def test_cada_cambio_queda_en_la_auditoria(client, h_admin, db):
    t = crear(client, h_admin)
    client.patch(f"{R}/{t['id']}", json={"lugar": "Coliseo"}, headers=h_admin)
    subir_anuncio(client, h_admin, t["id"])
    client.delete(f"{R}/{t['id']}", headers=h_admin)
    acciones = set(db.scalars(select(Auditoria.accion).where(Auditoria.entidad == "torneo_realizado")))
    assert acciones == {"club.torneo_realizado_crear", "club.torneo_realizado_editar",
                        "club.torneo_realizado_anuncio", "club.torneo_realizado_eliminar"}
