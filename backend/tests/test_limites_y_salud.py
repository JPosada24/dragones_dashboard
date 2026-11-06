"""Limitador de intentos en Postgres (compartido entre procesos) y salud del worker."""
from sqlalchemy import select, text

from app.core.limites import LimitadorFallos, purgar_intentos
from app.models.sistema import Intento
from app.worker import registrar_latido


def test_el_limite_se_comparte_entre_procesos(db):
    # Dos instancias = dos procesos de la API: antes cada una contaba por su lado y el límite se multiplicaba.
    proceso_a = LimitadorFallos("prueba", maximo=3, ventana_segundos=60)
    proceso_b = LimitadorFallos("prueba", maximo=3, ventana_segundos=60)
    proceso_a.registrar_fallo("203.0.113.9")
    proceso_b.registrar_fallo("203.0.113.9")
    assert proceso_a.segundos_bloqueo("203.0.113.9") == 0
    proceso_a.registrar_fallo("203.0.113.9")
    espera = proceso_b.segundos_bloqueo("203.0.113.9")
    assert 1 <= espera <= 61
    assert proceso_b.segundos_bloqueo("198.51.100.7") == 0  # otra IP no se afecta


def test_los_ambitos_no_se_mezclan(db):
    login = LimitadorFallos("login", maximo=1, ventana_segundos=60)
    sitio = LimitadorFallos("sitio", maximo=1, ventana_segundos=60)
    login.registrar_fallo("203.0.113.9")
    assert login.segundos_bloqueo("203.0.113.9") > 0
    assert sitio.segundos_bloqueo("203.0.113.9") == 0


def test_la_ip_no_se_guarda_en_claro(db):
    LimitadorFallos("login", maximo=5, ventana_segundos=60).registrar_fallo("203.0.113.9")
    claves = db.scalars(select(Intento.clave)).all()
    assert claves and all("203.0.113.9" not in c and len(c) == 64 for c in claves)


def test_solo_cuentan_los_intentos_dentro_de_la_ventana_y_el_worker_purga_los_viejos(db):
    limitador = LimitadorFallos("login", maximo=1, ventana_segundos=60)
    limitador.registrar_fallo("203.0.113.9")
    db.execute(text("UPDATE intentos SET creado_en = now() - interval '2 days'"))
    db.commit()
    assert limitador.segundos_bloqueo("203.0.113.9") == 0
    assert purgar_intentos(db) == "1 intentos viejos borrados"
    db.commit()
    assert db.scalar(select(Intento.id)) is None


def test_salud_del_worker(client, db):
    assert client.get("/api/v1/salud/worker").status_code == 503  # nunca ha corrido
    registrar_latido()
    r = client.get("/api/v1/salud/worker")
    assert r.status_code == 200 and r.json()["estado"] == "ok"
    db.execute(text("UPDATE latidos SET en = now() - interval '1 hour'"))
    db.commit()
    assert client.get("/api/v1/salud/worker").status_code == 503  # se detuvo


def test_salud_responde_a_head(client, db):
    # UptimeRobot revisa con HEAD: un 405 lo marcaba como caído aunque todo estuviera bien.
    assert client.head("/api/v1/salud").status_code == 200
    assert client.head("/api/v1/salud/worker").status_code == 503  # el worker nunca ha corrido
    registrar_latido()
    assert client.head("/api/v1/salud/worker").status_code == 200
