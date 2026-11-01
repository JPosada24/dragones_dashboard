"""Reportes de ingresos y exportación de movimientos (con permisos y protección contra fórmulas en el CSV)."""
import csv

from sqlalchemy import select

from app.models.sistema import Auditoria
from tests.fabrica import LUNES, I, T, alumno_inscrito, crear_torneo, inscribir_equipo

R = "/api/v1/reportes"


def _abonar(client, h, inscripcion_id, monto):
    r = client.post(f"{I}/{inscripcion_id}/pagos", json={"fecha_pago": LUNES.isoformat(), "monto": monto}, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _movimientos(client, h):
    alumno = alumno_inscrito(client, h)
    inscripcion = client.get(I, params={"alumno_id": alumno["id"]}, headers=h).json()[0]
    _abonar(client, h, inscripcion["id"], 30000)
    pagada = _abonar(client, h, inscripcion["id"], 20000)
    torneo = crear_torneo(client, h).json()
    equipo = inscribir_equipo(client, h, torneo["id"], club="=HYPERLINK(\"http://malo\")").json()
    r = client.post(f"{T}/{torneo['id']}/equipos/{equipo['id']}/pagos",
                    json={"monto": 50000, "fecha": LUNES.isoformat()}, headers=h)
    assert r.status_code == 200, r.text
    return pagada


def test_ingresos_por_mes_y_concepto_con_anulaciones_restando(client, h_admin, h_root):
    pagada = _movimientos(client, h_admin)
    abono = pagada["pagos"][1]
    r = client.post(f"{I}/{pagada['id']}/pagos/{abono['id']}/anular", json={}, headers=h_root)
    assert r.status_code == 200, r.text

    cuerpo = client.get(f"{R}/ingresos", params={"anio": LUNES.year}, headers=h_admin).json()
    noviembre = cuerpo["meses"][LUNES.month - 1]
    assert noviembre == {"mes": 11, "inscripciones": 30000, "multas": 0, "rifas": 0, "torneos": 50000, "total": 80000}
    assert cuerpo["total"] == 80000 and len(cuerpo["meses"]) == 12


def test_exportar_movimientos_en_csv_seguro(client, h_admin, h_root, db):
    _movimientos(client, h_admin)
    r = client.get(f"{R}/movimientos.csv", params={"desde": "2026-11-01", "hasta": "2026-11-30"}, headers=h_root)
    assert r.status_code == 200
    assert r.headers["content-disposition"].startswith("attachment;") and r.headers["cache-control"] == "no-store"
    lineas = r.content.decode("utf-8-sig").splitlines()
    assert lineas[0] == "fecha;concepto;referencia;detalle;monto"
    assert len(lineas) == 4  # dos abonos y el pago del torneo
    torneo = next(fila for fila in csv.reader(lineas[1:], delimiter=";") if fila[1] == "torneos")
    assert torneo[2].startswith("'=HYPERLINK")  # una celda que empieza por "=" no se vuelve fórmula en Excel
    assert db.scalar(select(Auditoria.accion).where(Auditoria.accion == "reportes.exportar"))


def test_permisos_de_reportes(client, h_admin, crear_usuario, auth_header):
    crear_usuario("coach@club.com", "ENTRENADOR")
    h_coach = auth_header("coach@club.com")
    rango = {"desde": "2026-11-01", "hasta": "2026-11-30"}
    assert client.get(f"{R}/ingresos", headers=h_coach).status_code == 403
    assert client.get(f"{R}/ingresos", headers=h_admin).status_code == 200
    assert client.get(f"{R}/movimientos.csv", params=rango, headers=h_admin).status_code == 403  # solo SuperAdmin


def test_el_rango_del_csv_se_valida(client, h_root):
    r = client.get(f"{R}/movimientos.csv", params={"desde": "2026-11-30", "hasta": "2026-11-01"}, headers=h_root)
    assert r.status_code == 422
