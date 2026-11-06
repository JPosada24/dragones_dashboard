"""Club ficticio del demo público. BORRA TODA LA BASE y la vuelve a llenar; solo corre con DEMO=true.

    python -m app.scripts.demo              # regenera una vez
    python -m app.scripts.demo --cada-noche # si la base está vacía la llena, y la regenera cada día a las 04:00

Los datos se crean usando la API real (en el mismo proceso) con un reloj simulado que avanza día a día durante seis
semanas: inscripciones con abonos, entrenamientos con asistencia, avisos, multas al cierre de cada día, una rifa con
talonarios y dos torneos. Así todo cumple las mismas reglas del club y el Resumen se ve como en un club de verdad.
Nombres, documentos y teléfonos son inventados (los teléfonos empiezan por 399, que no existe en Colombia, y los
correos son de example.com, reservado para ejemplos).
"""
import random
import sys
import time
from contextlib import contextmanager, suppress
from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app import worker
from app.core import fechas
from app.core.almacen import get_almacen
from app.core.config import get_settings
from app.core.demo import CLAVE_DEMO, CUENTAS_DEMO
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models.acceso import Usuario
from app.services import catalogos, usuarios

SEMANAS = 6
NOMBRES_F = ["Valentina", "Sofía", "Isabella", "Mariana", "Gabriela", "Daniela", "Salomé", "Luciana", "Sara",
             "Valeria", "Antonella", "Juliana", "Camila", "Laura", "Manuela", "Paula", "Natalia", "Emilia",
             "Ana María", "María José", "Luisa", "Catalina", "Andrea", "Alejandra", "Verónica", "Juana",
             "Ximena", "Carolina", "Mía", "Victoria", "Elena", "Abril"]
NOMBRES_M = ["Santiago", "Sebastián", "Matías", "Samuel", "Alejandro", "Nicolás", "Juan José", "Tomás",
             "Emiliano", "Daniel", "Martín", "Gabriel", "David", "Felipe", "Andrés", "Mateo", "Jerónimo",
             "Simón", "Lucas", "Esteban", "Julián", "Miguel Ángel", "Joaquín", "Pablo", "Iván", "Diego",
             "Óscar", "Camilo"]
APELLIDOS = ["Restrepo", "Giraldo", "Ospina", "Cardona", "Zapata", "Arango", "Montoya", "Henao", "Valencia",
             "Quintero", "Londoño", "Correa", "Mejía", "Agudelo", "Castaño", "Vélez", "Muñoz", "Patiño",
             "Ríos", "Salazar", "Toro", "Uribe", "Betancur", "Escobar", "Álvarez", "Gaviria", "Duque", "Marín"]
CLUBES = [("Halcones VC", "Medellín"), ("Titanes Voley", "Envigado"), ("Club Cóndor", "Bello"),
          ("Águilas del Sur", "Itagüí"), ("Tiburones VC", "Rionegro"), ("Club Pumas", "Sabaneta"),
          ("Fénix Voleibol", "La Estrella"), ("Linces VC", "Caldas"), ("Club Jaguares", "Copacabana"),
          ("Delfines Voley", "Girardota"), ("Club Centauros", "Marinilla"), ("Osos VC", "Guarne")]


class Reloj:
    """Reemplaza la hora del club (fechas.ahora): todo el código la pide por ahí."""

    def __init__(self) -> None:
        self.momento: datetime | None = None
        self._original = fechas.ahora

    def poner(self, dia: date, hh: int = 8, mm: int = 0) -> None:
        self.momento = datetime(dia.year, dia.month, dia.day, hh, mm, tzinfo=fechas.ZONA_CLUB)
        fechas.ahora = lambda: self.momento  # type: ignore[assignment]

    def soltar(self) -> None:
        fechas.ahora = self._original  # type: ignore[assignment]


@contextmanager
def reloj_simulado():
    r = Reloj()
    try:
        yield r
    finally:
        r.soltar()


def vaciar() -> None:
    """TRUNCATE no dispara los triggers de solo-agregar (son por fila): el demo sí se puede borrar entero."""
    tablas = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE TABLE {tablas} RESTART IDENTITY CASCADE"))
    almacen = get_almacen()
    raiz = getattr(almacen, "raiz", None)
    if raiz is not None:
        for archivo in raiz.glob("*"):
            if archivo.is_file():
                archivo.unlink()


class Demo:
    def __init__(self, client: TestClient, reloj: Reloj, azar: random.Random) -> None:
        self.c, self.reloj, self.azar = client, reloj, azar
        self.h: dict[str, str] = {}
        self.documento = 1_000_000_000
        self.alumnos: list[dict] = []
        self.inscripciones: dict[str, dict] = {}  # alumno_id -> inscripción

    # ---------- utilidades ----------
    def pedir(self, metodo: str, ruta: str, **kw) -> dict | list:
        r = self.c.request(metodo, f"/api/v1{ruta}", headers=self.h, **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"{metodo} {ruta} -> {r.status_code}: {r.text[:300]}")
        return r.json() if r.content else {}

    def entrar(self, email: str) -> None:
        r = self.c.post("/api/v1/auth/login", json={"email": email, "password": CLAVE_DEMO})
        r.raise_for_status()
        self.h = {"Authorization": f"Bearer {r.json()['access_token']}"}

    def doc(self) -> str:
        self.documento += self.azar.randint(1, 9_000)
        return str(self.documento)

    def telefono(self) -> str:
        return f"399{self.azar.randint(1_000_000, 9_999_999)}"

    def tareas_del_worker(self) -> None:
        for tarea in worker.tareas():
            worker.ejecutar(tarea)

    # ---------- club ----------
    def club(self, inicio: date) -> None:
        self.pedir("PUT", "/sesiones/horario", json={"dias": [
            {"dia_semana": 0, "hora_inicio": "18:00", "hora_fin": "20:00", "lugar": "Coliseo del barrio"},
            {"dia_semana": 2, "hora_inicio": "18:00", "hora_fin": "20:00", "lugar": "Coliseo del barrio"},
            {"dia_semana": 5, "hora_inicio": "08:00", "hora_fin": "10:30", "lugar": "Coliseo del barrio"},
        ]})
        self.pedir("PATCH", "/club/perfil", json={
            "lema": "Garra, disciplina y voleibol", "ciudad": "Medellín", "sede": "Coliseo del barrio",
            "fundado_en": 2019, "whatsapp": "3990000000", "correo": "contacto@example.com",
            "mision": "Formar deportistas íntegros a través del voleibol, con disciplina, respeto y trabajo en equipo.",
            "vision": "Ser el club de voleibol de referencia del Valle de Aburrá por su formación y sus resultados.",
            "historia": "El club nació en 2019 con doce jugadoras en una cancha de barrio. Hoy entrena a niñas, niños "
                        "y jóvenes en las ramas femenina y masculina.",
        })
        for nombre, cargo, orden in (("Julián Demo", "Entrenador principal", 0),
                                     ("Carlos Demo", "Entrenador asistente · Iniciación", 1),
                                     ("Andrea Demo", "Coordinación y administración", 2)):
            self.pedir("POST", "/club/equipo", json={"nombre": nombre, "cargo": cargo, "orden": orden})

    def alumno(self, rama: str, edad: int, fecha_inscripcion: date) -> dict:
        nombre = self.azar.choice(NOMBRES_F if rama == "femenina" else NOMBRES_M)
        apellido1, apellido2 = self.azar.sample(APELLIDOS, 2)
        nacimiento = date(fechas.hoy().year - edad, self.azar.randint(1, 12), self.azar.randint(1, 28))
        edad = fechas.edad(nacimiento, fechas.hoy())  # la real: depende del mes de nacimiento
        datos: dict = {
            "nombres": nombre, "apellidos": f"{apellido1} {apellido2}", "tipo_documento": "CC" if edad >= 18 else "TI",
            "documento": self.doc(), "fecha_nacimiento": nacimiento.isoformat(), "rama": rama,
            "nivel": "avanzado" if edad >= 15 and self.azar.random() < 0.5 else "iniciacion",
            "autorizacion": {"nombre": f"{nombre} {apellido1}", "imagen": self.azar.random() < 0.8},
        }
        if edad < 18:
            acudiente = self.pedir("POST", "/acudientes", json={
                "nombres": self.azar.choice(NOMBRES_F + NOMBRES_M),
                "apellidos": f"{apellido1} {self.azar.choice(APELLIDOS)}",
                "tipo_documento": "CC", "documento": self.doc(), "telefono": self.telefono(),
                "email": f"acudiente{len(self.alumnos) + 1}@example.com",
            })
            parentesco = self.azar.choice(["madre", "padre"])
            datos["acudientes"] = [{"acudiente_id": acudiente["id"], "parentesco": parentesco}]
            datos["autorizacion"]["nombre"] = f"{acudiente['nombres']} {acudiente['apellidos']}"
        a = self.pedir("POST", "/alumnos", json=datos)
        i = self.pedir("POST", "/inscripciones",
                       json={"alumno_id": a["id"], "fecha_inscripcion": fecha_inscripcion.isoformat()})
        self.alumnos.append(a)
        self.inscripciones[a["id"]] = i
        return a

    def abonar(self, alumno_id: str, monto: int, dia: date) -> None:
        i = self.inscripciones[alumno_id]
        with suppress(RuntimeError):  # ya pagó todo o venció: en un club real también pasa
            self.inscripciones[alumno_id] = self.pedir(
                "POST", f"/inscripciones/{i['id']}/pagos", json={"fecha_pago": dia.isoformat(), "monto": monto})

    # ---------- días ----------
    def entrenamiento(self, dia: date) -> None:
        sesiones = self.pedir("GET", f"/sesiones?desde={dia}&hasta={dia}")
        for s in sesiones:
            if s.get("cancelada"):
                continue
            planilla = self.pedir("GET", f"/sesiones/{s['id']}/asistencia")
            if not planilla:
                continue
            ids = [f["alumno_id"] for f in planilla]
            # Al mediodía algunos avisan que no van (basta con avisar): queda justificado.
            self.reloj.poner(dia, 12)
            avisan = set(self.azar.sample(ids, k=max(0, round(len(ids) * 0.05))))
            for a in avisan:
                self.pedir("POST", f"/sesiones/{s['id']}/justificaciones", json={"alumno_id": a})
            # En el entrenamiento el entrenador marca a los que llegaron; los demás quedan ausentes al cierre.
            self.reloj.poner(dia, int(s["hora_inicio"][:2]) + 1)
            vinieron = [a for a in ids if a not in avisan and self.azar.random() < 0.86]
            if vinieron:
                self.pedir("POST", f"/sesiones/{s['id']}/asistencia",
                           json={"marcas": [{"alumno_id": a, "estado": "presente"} for a in vinieron]})

    def cobros_del_dia(self, dia: date, rifa: dict | None) -> None:
        self.reloj.poner(dia, 17)
        multas = [m for m in self.pedir("GET", "/multas?estado=pendiente") if self.azar.random() < 0.12]
        if multas:
            self.pedir("POST", "/multas/pagos", json={"multa_ids": [m["id"] for m in multas][:100],
                                                       "fecha_pago": dia.isoformat()})
        for alumno_id, i in list(self.inscripciones.items()):
            saldo = i.get("saldo", 0)
            if i.get("estado") == "pendiente_pago" and saldo and self.azar.random() < 0.05:
                self.abonar(alumno_id, saldo if self.azar.random() < 0.6 else min(saldo, 30_000), dia)
        if rifa:
            for t in self.pedir("GET", f"/rifas/{rifa['id']}/talonarios"):
                if t["saldo"] and self.azar.random() < 0.07:
                    monto = t["saldo"] if self.azar.random() < 0.5 else min(t["saldo"], 20_000)
                    self.pedir("POST", f"/rifas/{rifa['id']}/talonarios/{t['id']}/pagos",
                               json={"monto": monto, "fecha": dia.isoformat()})

    def torneo(self, nombre: str, rama: str, inicio: date, clubes: int, pagan: float) -> dict:
        t = self.pedir("POST", "/torneos", json={
            "nombre": nombre, "rama": rama, "fecha_inicio": inicio.isoformat(),
            "fecha_fin": (inicio + timedelta(days=1)).isoformat(),
            "fecha_limite_inscripcion": (inicio - timedelta(days=4)).isoformat(),
            "lugar": "Coliseo del barrio", "cupo_equipos": 12, "valor_inscripcion": 150_000,
        })
        for club, ciudad in self.azar.sample(CLUBES, clubes):
            e = self.pedir("POST", f"/torneos/{t['id']}/equipos", json={
                "nombre_club": club, "ciudad": ciudad, "delegado_nombre": f"{self.azar.choice(NOMBRES_M + NOMBRES_F)} "
                f"{self.azar.choice(APELLIDOS)}", "delegado_telefono": self.telefono()})
            if self.azar.random() < pagan:
                monto = 150_000 if self.azar.random() < 0.7 else 75_000
                self.pedir("POST", f"/torneos/{t['id']}/equipos/{e['id']}/pagos",
                           json={"monto": monto, "fecha": fechas.hoy().isoformat()})
        return t


def generar(semilla: int | None = None) -> None:
    s = get_settings()
    if not s.demo:
        sys.exit("Este script BORRA la base: solo corre en el demo (DEMO=true).")
    hoy = fechas.hoy()
    azar = random.Random(semilla if semilla is not None else hoy.toordinal())  # noqa: S311  (datos de ejemplo)
    from app.main import app  # después de validar DEMO: crea la app con las restricciones del demo

    vaciar()
    with SessionLocal() as db:
        catalogos.sembrar_catalogos(db)
        for rol, email, nombre in CUENTAS_DEMO[:3]:
            usuarios.crear_usuario(db, email=email, nombre=nombre, password=CLAVE_DEMO, rol_codigo=rol)
        db.commit()

    inicio = hoy - timedelta(weeks=SEMANAS)
    with reloj_simulado() as reloj, TestClient(app, base_url="https://demo.local") as client:
        d = Demo(client, reloj, azar)
        reloj.poner(inicio, 8)
        d.entrar("superadmin@example.com")
        d.club(inicio)

        # Alumnos: la mayoría ya inscritos al empezar; unos pocos llegan en las semanas siguientes.
        llegadas = sorted(inicio + timedelta(days=azar.choice([-25, -18, -12, -6, -2, 0, 0, 3, 9, 16, 24, 30]))
                          for _ in range(58))
        pendientes = []
        for n, dia in enumerate(llegadas):
            rama = "femenina" if n % 9 < 5 else "masculina"
            pendientes.append((dia, rama, azar.choice([10, 11, 12, 13, 14, 15, 15, 16, 17, 18, 19, 21, 24])))

        def inscribir_hasta(dia: date) -> None:
            while pendientes and pendientes[0][0] <= dia:
                fecha, rama, edad = pendientes.pop(0)
                a = d.alumno(rama, edad, fecha)
                forma = azar.random()
                if forma < 0.55:
                    d.abonar(a["id"], 90_000, fecha)
                elif forma < 0.82:
                    d.abonar(a["id"], azar.choice([30_000, 40_000, 50_000]), fecha)

        inscribir_hasta(inicio)
        d.tareas_del_worker()
        dia_torneo = min(inicio + timedelta(days=19), hoy - timedelta(days=3))  # ya jugado al llegar a hoy
        torneo_pasado = d.torneo("Copa Dragones de Integración", "femenina", dia_torneo, 9, 0.85)
        rifa = None

        dia = inicio
        while dia < hoy:
            reloj.poner(dia, 7)
            inscribir_hasta(dia)
            d.tareas_del_worker()  # programa sesiones, vence inscripciones, mora…
            if dia == inicio + timedelta(days=3):
                rifa = d.pedir("POST", "/rifas", json={"nombre": "Rifa de fin de año", "anio": hoy.year,
                                                       "premio": "Balón oficial y uniforme del club",
                                                       "fecha_sorteo": (hoy + timedelta(days=18)).isoformat()})
            if rifa and dia.weekday() == 0:
                reloj.poner(dia, 9)
                d.pedir("POST", f"/rifas/{rifa['id']}/talonarios")  # los recién inscritos reciben su talonario
            d.entrenamiento(dia)
            d.cobros_del_dia(dia, rifa)
            dia += timedelta(days=1)
            reloj.poner(dia, 0, 10)
            d.tareas_del_worker()  # cierre del día anterior: ausentes y multas

        # Hoy, con la hora real: el próximo torneo (inscripciones abiertas) y el pasado, a «Torneos realizados».
        reloj.soltar()
        d.tareas_del_worker()
        d.torneo("Torneo Relámpago Dragones", "masculina", hoy + timedelta(days=24), 5, 0.5)
        realizado = d.pedir("POST", f"/torneos/{torneo_pasado['id']}/realizado")
        d.pedir("PATCH", f"/club/torneos-realizados/{realizado['id']}", json={
            "resumen": "Campeón: Halcones VC. Subcampeón: Club Dragones. 9 clubes de 7 municipios.", "publicado": True})

        # La cuenta de la familia: el acudiente de dos alumnos.
        with SessionLocal() as db:
            raiz = db.scalar(select(Usuario).where(Usuario.email == "superadmin@example.com"))
            hermanos = [a for a in d.alumnos if a.get("acudientes")]
            acudiente_id = d.pedir("GET", f"/alumnos/{hermanos[0]['id']}")["acudientes"][0]["acudiente_id"]
            d.pedir("POST", f"/alumnos/{hermanos[1]['id']}/acudientes",
                    json={"acudiente_id": acudiente_id, "parentesco": "madre"})
            rol, email, nombre = CUENTAS_DEMO[3]
            usuarios.crear_cuenta(db, {"email": email, "nombre": nombre, "password": CLAVE_DEMO, "rol": rol,
                                       "vincular_acudiente_id": acudiente_id}, actor=raiz, ip=None)
            db.commit()
    print(f"Demo listo: {len(d.alumnos)} alumnos, desde {inicio} hasta hoy.")


def segundos_hasta(hh: int) -> float:  # pragma: no cover
    ahora = fechas.ahora()
    siguiente = ahora.replace(hour=hh, minute=0, second=0, microsecond=0)
    if siguiente <= ahora:
        siguiente += timedelta(days=1)
    return (siguiente - ahora).total_seconds()


def main() -> None:  # pragma: no cover  (entrada de la línea de comandos)
    if "--cada-noche" not in sys.argv:
        generar()
        return
    with SessionLocal() as db:
        vacia = db.scalar(select(Usuario.id).limit(1)) is None
    if vacia:
        generar()
    while True:  # pragma: no cover  (bucle del contenedor: corre hasta que lo detengan)
        time.sleep(segundos_hasta(4))
        try:
            generar()
        except Exception as e:
            print(f"El reinicio del demo falló: {e}", flush=True)


if __name__ == "__main__":
    main()
