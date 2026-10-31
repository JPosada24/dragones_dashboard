"""Asistente de IA: se prueba con un cliente falso de la API de Claude (sin red ni gasto)."""
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.api.v1.agente import get_ia
from app.main import app
from app.models.sistema import UsoAgente
from tests.fabrica import alumno_inscrito

URL = "/api/v1/agente/preguntar"


def texto(t: str):
    return SimpleNamespace(type="text", text=t)


def usar(nombre: str, entrada: dict | None = None, ident: str = "t1"):
    return SimpleNamespace(type="tool_use", id=ident, name=nombre, input=entrada or {})


class ClaudeFalso:
    """Devuelve respuestas guionizadas y guarda lo que recibió cada llamada."""

    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.llamadas: list[dict] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._crear))

    def _crear(self, **kw):
        self.llamadas.append({**kw, "messages": list(kw["messages"])})  # copia: la lista sigue creciendo
        contenido = self.respuestas.pop(0) if self.respuestas else [usar("buscar_alumnos")]
        motivo = "tool_use" if any(b.type == "tool_use" for b in contenido) else "end_turn"
        uso = SimpleNamespace(input_tokens=100, output_tokens=20, cache_read_input_tokens=50)
        return SimpleNamespace(content=contenido, stop_reason=motivo, usage=uso)

    def herramientas_ofrecidas(self) -> set[str]:
        return {t["name"] for t in self.llamadas[0]["tools"]}

    def resultado(self, n: int = 1) -> dict:
        """El tool_result que se le devolvió al modelo en la llamada n."""
        return self.llamadas[n]["messages"][-1]["content"][0]


@pytest.fixture
def claude():
    def _instalar(*respuestas):
        falso = ClaudeFalso(*respuestas)
        app.dependency_overrides[get_ia] = lambda: falso
        return falso

    yield _instalar
    app.dependency_overrides.pop(get_ia, None)


def test_la_familia_solo_consulta_lo_suyo_y_sin_datos_sensibles(client, h_admin, familia, claude, db):
    otra = alumno_inscrito(client, h_admin, documento="2000000009")
    ia = claude([usar("buscar_alumnos")], [texto("Tienes una hija inscrita.")])
    r = client.post(URL, json={"pregunta": "¿Qué hijos tengo?"}, headers=familia["h"])
    assert r.status_code == 200, r.text
    assert r.json()["texto"] == "Tienes una hija inscrita." and r.json()["herramientas"] == ["buscar_alumnos"]

    ofrecidas = ia.herramientas_ofrecidas()
    assert "buscar_alumnos" in ofrecidas and not {"resumen_del_club", "riesgo_de_mora", "torneos"} & ofrecidas
    resultado = ia.resultado()
    datos = json.loads(resultado["content"])
    assert [a["codigo"] for a in datos] == [familia["hija"]["codigo"]]  # no aparece la otra alumna
    assert otra["codigo"] not in resultado["content"]
    for sensible in ("documento", "telefono", "email", "direccion", "eps", "\"id\""):
        assert sensible not in resultado["content"]
    # Se registra el uso (sin la pregunta ni la respuesta).
    [uso] = db.scalars(select(UsoAgente)).all()
    assert (uso.tokens_entrada, uso.tokens_salida, uso.herramientas) == (200, 40, ["buscar_alumnos"])


def test_alumno_ajeno_o_herramienta_no_permitida_devuelven_error_al_modelo(client, h_admin, familia, claude):
    otra = alumno_inscrito(client, h_admin, documento="2000000009")
    ia = claude([usar("estado_de_cuenta", {"codigo": otra["codigo"]})], [usar("resumen_del_club")], [texto("No.")])
    assert client.post(URL, json={"pregunta": "¿Cuánto debe?"}, headers=familia["h"]).status_code == 200
    ajeno, prohibido = ia.resultado(1), ia.resultado(2)
    assert ajeno["is_error"] and "No hay un alumno" in ajeno["content"]
    assert prohibido["is_error"] and "no disponible" in prohibido["content"]


def test_el_staff_consulta_el_estado_de_cuenta_por_codigo(client, h_admin, claude):
    alumna = alumno_inscrito(client, h_admin)
    ia = claude([usar("estado_de_cuenta", {"codigo": alumna["codigo"].lower()})], [texto("Debe la inscripción.")])
    assert client.post(URL, json={"pregunta": "¿Cuánto debe?"}, headers=h_admin).status_code == 200
    datos = json.loads(ia.resultado()["content"])
    assert datos["inscripcion_saldo"] == 90000 and datos["al_dia"] is False
    assert {"resumen_del_club", "riesgo_de_mora", "torneos"} <= ia.herramientas_ofrecidas()


def test_el_bucle_de_herramientas_tiene_tope(client, h_admin, claude):
    ia = claude()  # siempre pide otra herramienta
    r = client.post(URL, json={"pregunta": "Dame todo"}, headers=h_admin)
    assert r.status_code == 200 and "demasiados pasos" in r.json()["texto"]
    assert len(ia.llamadas) == 6


def test_limite_diario_y_apagado(client, h_admin, h_root, claude):
    claude([texto("Hola")], [texto("Hola")])
    client.patch("/api/v1/configuracion/agente_mensajes_por_dia", json={"valor": 1}, headers=h_root)
    primera = client.post(URL, json={"pregunta": "Hola"}, headers=h_admin)
    assert primera.status_code == 200 and primera.json()["restantes_hoy"] == 0
    r = client.post(URL, json={"pregunta": "Hola"}, headers=h_admin)
    assert r.status_code == 429 and "límite" in r.json()["detail"]
    estado = client.get("/api/v1/agente/estado", headers=h_admin).json()
    assert (estado["limite_diario"], estado["usados_hoy"]) == (1, 1)

    client.patch("/api/v1/configuracion/agente_mensajes_por_dia", json={"valor": 0}, headers=h_root)
    assert client.post(URL, json={"pregunta": "Hola"}, headers=h_root).status_code == 503


def test_sin_clave_de_la_api_no_esta_configurado(client, h_admin):
    r = client.post(URL, json={"pregunta": "Hola"}, headers=h_admin)
    assert r.status_code == 503 and "ANTHROPIC_API_KEY" in r.json()["detail"]
    assert client.get("/api/v1/agente/estado", headers=h_admin).json()["configurado"] is False


def test_validaciones_de_entrada(client, h_admin, claude):
    claude()
    assert client.post(URL, json={"pregunta": "Hola"}).status_code == 401
    historial = [{"rol": "assistant", "texto": "Hola"}]
    assert client.post(URL, json={"pregunta": "Hola", "historial": historial}, headers=h_admin).status_code == 422
    assert client.post(URL, json={"pregunta": "x" * 2001}, headers=h_admin).status_code == 422
    assert client.post(URL, json={"pregunta": "Hola", "modelo": "otro"}, headers=h_admin).status_code == 422


def test_el_historial_se_reenvia_y_la_negativa_se_maneja(client, h_admin, claude):
    ia = claude([texto("ignorado")])
    ia.beta.messages.create = lambda **kw: (ia.llamadas.append(kw), SimpleNamespace(
        content=[], stop_reason="refusal",
        usage=SimpleNamespace(input_tokens=5, output_tokens=0, cache_read_input_tokens=0)))[1]
    historial = [{"rol": "user", "texto": "Hola"}, {"rol": "assistant", "texto": "¿En qué ayudo?"}]
    r = client.post(URL, json={"pregunta": "Otra cosa", "historial": historial}, headers=h_admin)
    assert r.status_code == 200 and "No puedo ayudar" in r.json()["texto"]
    mensajes = ia.llamadas[0]["messages"]
    assert [m["role"] for m in mensajes] == ["user", "assistant", "user"]
    assert mensajes[-1]["content"].endswith("Otra cosa") and "Hoy es" in mensajes[-1]["content"]
