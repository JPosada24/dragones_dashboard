"""El contrato OpenAPI guardado (del que salen los tipos del frontend) debe ser el de la API actual.

Si falla: la API cambió y nadie regeneró los tipos. Desde la raíz del proyecto:
    docker compose exec -T api python -m app.scripts.openapi > frontend/openapi/openapi.json
    cd frontend && npm run api:tipos
"""
import json
from pathlib import Path

import pytest

from app.main import app

CONTRATO = Path(__file__).resolve().parents[2] / "frontend" / "openapi" / "openapi.json"


@pytest.mark.skipif(not CONTRATO.exists(), reason="el frontend no está montado (en el CI sí está y se compara)")
def test_el_contrato_del_frontend_esta_al_dia():
    guardado = json.loads(CONTRATO.read_text(encoding="utf-8"))
    actual = json.loads(json.dumps(app.openapi()))  # mismo tratamiento de tipos que al exportarlo
    assert guardado == actual, "La API cambió: regenera frontend/openapi/openapi.json y los tipos (ver arriba)."
