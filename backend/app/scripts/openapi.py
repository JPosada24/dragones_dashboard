"""Escribe el contrato OpenAPI de la API (de él salen los tipos del frontend).

    python -m app.scripts.openapi > ../frontend/openapi/openapi.json

Sale ordenado y con formato estable para que el CI pueda comparar: si el contrato cambió y nadie regeneró los
tipos del frontend, la comparación falla.
"""
import json
import sys

from app.main import app


def main() -> None:
    json.dump(app.openapi(), sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
