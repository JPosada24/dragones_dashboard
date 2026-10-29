"""Uso:  python -m app.scripts.seed"""
from app.db.session import SessionLocal
from app.services.catalogos import sembrar_catalogos, sembrar_superadmin


def main() -> None:
    with SessionLocal() as db:
        sembrar_catalogos(db)
        print("Catálogos (permisos, roles, parámetros) sincronizados.")
        print(sembrar_superadmin(db))


if __name__ == "__main__":
    main()
