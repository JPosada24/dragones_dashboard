"""Sitio público del club: panel de edición (club.editar) y vista/inscripción sin sesión."""
import io

import pytest
from PIL import Image
from sqlalchemy import select

from app.models.notificaciones import Notificacion
from app.models.torneos import EquipoTorneo
from app.services.club import youtube_id
from app.services.errores import ErrorNegocio
from tests.fabrica import T, crear_torneo

C = "/api/v1/club"
P = "/api/v1/publico"


def jpeg_con_gps(ancho=3000, alto=2000) -> bytes:
    """JPEG con metadatos EXIF (incluida una ubicación GPS) para comprobar que se quitan."""
    imagen = Image.new("RGB", (ancho, alto), (242, 105, 30))
    exif = Image.Exif()
    exif[0x010F] = "Telefono de prueba"  # fabricante
    exif[0x8825] = {1: "N", 2: (5.0, 4.0, 3.0)}  # GPSInfo
    salida = io.BytesIO()
    imagen.save(salida, "JPEG", exif=exif)
    return salida.getvalue()


def publicar(client, h, **perfil):
    r = client.patch(f"{C}/perfil", json={"publicado": True, **perfil}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def album(client, h, publicado=True):
    r = client.post(f"{C}/albumes", json={"nombre": "Copa Caldas", "publicado": publicado}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def subir(client, h, album_id, datos: bytes, autorizacion="true"):
    return client.post(f"{C}/albumes/{album_id}/fotos", data={"autorizacion": autorizacion},
                       files={"archivo": ("foto.jpg", datos, "image/jpeg")}, headers=h)


def test_solo_quien_edita_el_club_entra_al_panel(client, h_admin, crear_usuario, auth_header):
    assert client.get(C, headers=h_admin).status_code == 200
    crear_usuario("coach@club.com", "ENTRENADOR")
    h = auth_header("coach@club.com")
    assert client.get(C, headers=h).status_code == 403
    assert client.patch(f"{C}/perfil", json={"lema": "x"}, headers=h).status_code == 403
    assert client.get(C).status_code == 401


def test_el_sitio_solo_se_ve_publicado_y_solo_con_lo_publicado(client, h_admin):
    assert client.get(f"{P}/club").status_code == 404
    publicar(client, h_admin, lema="Garra y corazón", instagram="https://instagram.com/dragones.vb/")
    album(client, h_admin, publicado=False)
    client.post(f"{C}/videos", json={"titulo": "Borrador", "enlace": "https://youtu.be/dQw4w9WgXcQ",
                                     "publicado": False}, headers=h_admin)
    client.post(f"{C}/videos", json={"titulo": "Resumen", "enlace": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
                headers=h_admin)
    client.post(f"{C}/equipo", json={"nombre": "Ana Ruiz", "cargo": "Entrenadora", "publicado": False},
                headers=h_admin)
    sitio = client.get(f"{P}/club").json()
    assert sitio["perfil"]["lema"] == "Garra y corazón" and sitio["perfil"]["instagram"] == "dragones.vb"
    assert sitio["albumes"] == [] and sitio["equipo"] == []  # borradores y álbumes vacíos no salen
    assert [v["titulo"] for v in sitio["videos"]] == ["Resumen"]
    client.put("/api/v1/sesiones/horario", headers=h_admin, json={"dias": [
        {"dia_semana": 0, "hora_inicio": "18:00", "hora_fin": "20:00", "lugar": "Coliseo"}]})
    [dia] = client.get(f"{P}/club").json()["horario"]
    assert (dia["dia_semana"], dia["hora_inicio"], dia["lugar"]) == (0, "18:00:00", "Coliseo")


def test_la_foto_se_procesa_sin_metadatos_y_se_publica_con_su_album(client, h_admin, db):
    publicar(client, h_admin)
    a = album(client, h_admin, publicado=False)
    assert subir(client, h_admin, a["id"], jpeg_con_gps(), autorizacion="false").status_code == 422
    assert subir(client, h_admin, a["id"], b"%PDF-1.4 no es una foto").status_code == 422
    r = subir(client, h_admin, a["id"], jpeg_con_gps())
    assert r.status_code == 201, r.text
    foto = r.json()
    assert (foto["ancho"], foto["alto"]) == (1920, 1280)

    # El panel la ve (vista previa); el sitio no, mientras el álbum no esté publicado.
    previa = client.get(f"{C}/fotos/{foto['id']}?tam=grande", headers=h_admin)
    assert previa.status_code == 200 and previa.headers["cache-control"] == "private, no-store"
    with Image.open(io.BytesIO(previa.content)) as im:
        assert im.format == "JPEG" and not im.getexif()  # sin fabricante ni GPS
    assert client.get(f"{P}/fotos/{foto['id']}").status_code == 404

    client.patch(f"{C}/albumes/{a['id']}", json={"publicado": True}, headers=h_admin)
    publica = client.get(f"{P}/fotos/{foto['id']}")
    assert publica.status_code == 200 and "public" in publica.headers["cache-control"]
    with Image.open(io.BytesIO(publica.content)) as im:
        assert max(im.size) == 480  # miniatura
    assert [x["nombre"] for x in client.get(f"{P}/club").json()["albumes"]] == ["Copa Caldas"]

    assert client.delete(f"{C}/albumes/{a['id']}", headers=h_admin).status_code == 204
    assert client.get(f"{P}/fotos/{foto['id']}").status_code == 404


@pytest.mark.parametrize("enlace", [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10", "https://youtu.be/dQw4w9WgXcQ",
    "https://youtube.com/shorts/dQw4w9WgXcQ", "https://www.youtube.com/embed/dQw4w9WgXcQ",
])
def test_enlaces_de_youtube(enlace):
    assert youtube_id(enlace) == "dQw4w9WgXcQ"


@pytest.mark.parametrize("enlace", [
    "https://vimeo.com/123", "javascript:alert(1)", "https://youtube.com.evil.com/watch?v=dQw4w9WgXcQ",
    "https://www.youtube.com/watch?v=corto",
])
def test_enlaces_que_no_son_de_youtube(enlace):
    with pytest.raises(ErrorNegocio):
        youtube_id(enlace)


def test_redes_sociales_solo_el_usuario(client, h_admin):
    r = client.patch(f"{C}/perfil", json={"instagram": "@dragones"}, headers=h_admin)
    assert r.json()["instagram"] == "dragones"
    assert client.patch(f"{C}/perfil", json={"facebook": "https://evil.com/<script>"},
                        headers=h_admin).status_code == 422
    assert client.patch(f"{C}/perfil", json={"nombre": ""}, headers=h_admin).status_code == 422


DATOS_CLUB = {
    "nombre_club": "Halcones VC", "ciudad": "Pereira", "delegado_nombre": "Carlos Gómez",
    "delegado_telefono": "3001234567", "delegado_email": "carlos@halcones.co", "acepta_datos": True,
}


def test_un_club_se_inscribe_desde_el_sitio_y_se_avisa_al_staff(client, h_admin, reloj, db):
    torneo = crear_torneo(client, h_admin).json()
    url = f"{P}/torneos/{torneo['id']}/inscripcion"
    assert client.post(url, json=DATOS_CLUB).status_code == 404  # el sitio aún no está publicado
    publicar(client, h_admin)
    [abierto] = client.get(f"{P}/club").json()["torneos"]
    assert abierto["cupos_libres"] == 18 and abierto["valor_inscripcion"] == 150000
    assert "delegado" not in str(abierto)

    assert client.post(url, json={**DATOS_CLUB, "acepta_datos": False}).status_code == 422
    assert client.post(url, json={**DATOS_CLUB, "estado": "confirmado"}).status_code == 422
    r = client.post(url, json=DATOS_CLUB)
    assert r.status_code == 201, r.text
    assert r.json()["estado"] == "pendiente_pago" and r.json()["valor"] == 150000
    equipo = db.scalar(select(EquipoTorneo))
    assert equipo.origen == "sitio" and equipo.autoriza_datos_en is not None and equipo.inscrito_por is None
    avisos = db.scalars(select(Notificacion).where(Notificacion.tipo == "torneo_inscripcion_sitio")).all()
    assert avisos and "Halcones VC" in avisos[0].titulo
    # El staff lo ve en el torneo, marcado como inscrito desde el sitio.
    [visto] = client.get(f"{T}/{torneo['id']}/equipos", headers=h_admin).json()
    assert visto["origen"] == "sitio"
    assert client.post(url, json=DATOS_CLUB).status_code == 409  # mismo club dos veces


def test_trampa_de_bots_y_limite_por_ip(client, h_admin, reloj, db):
    torneo = crear_torneo(client, h_admin).json()
    publicar(client, h_admin)
    url = f"{P}/torneos/{torneo['id']}/inscripcion"
    r = client.post(url, json={**DATOS_CLUB, "sitio_web": "http://spam.example"})
    assert r.status_code == 201 and db.scalar(select(EquipoTorneo)) is None  # parece aceptado, no se guarda
    for i in range(4):
        client.post(url, json={**DATOS_CLUB, "nombre_club": f"Club {i}"})
    r = client.post(url, json={**DATOS_CLUB, "nombre_club": "Uno más"})
    assert r.status_code == 429
