"""Vuelve a cifrar todo con la clave vigente (la primera de DATA_ENCRYPTION_KEY).

    1. En .env:  DATA_ENCRYPTION_KEY={nueva},{vieja}
    2. docker compose stop api worker
    3. docker compose run --rm api python -m app.scripts.rotar_clave
    4. En .env:  DATA_ENCRYPTION_KEY={nueva}     (guarda la vieja hasta tener un respaldo hecho con la nueva)
    5. docker compose up -d

Reescribe: documentos de identidad de alumnos y acudientes (y su índice ciego, que depende de la clave) y los
archivos subidos a la ficha. Es idempotente: si se corta, se vuelve a correr.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core import cifrado
from app.core.almacen import Almacen, get_almacen
from app.db.session import SessionLocal
from app.models.alumnos import Acudiente, Alumno, DocumentoAlumno
from app.services import auditoria


def rotar(db: Session, almacen: Almacen) -> dict[str, int]:
    personas = 0
    for modelo in (Alumno, Acudiente):
        for p in db.scalars(select(modelo)):
            numero = cifrado.descifrar(p.documento_cifrado)
            p.documento_cifrado = cifrado.cifrar(numero)
            p.documento_indice = cifrado.indice_ciego(f"{p.tipo_documento}:{numero}")
            personas += 1
    archivos = 0
    for doc in db.scalars(select(DocumentoAlumno)):
        # Antes del commit: si algo falla después, el archivo sigue legible porque ambas claves siguen configuradas.
        almacen.guardar(doc.clave_almacen, cifrado.recifrar(almacen.leer(doc.clave_almacen)))
        archivos += 1
    resumen = {"documentos_identidad": personas, "archivos": archivos}
    auditoria.registrar(db, accion="sistema.rotar_clave", entidad="sistema", entidad_id="cifrado",
                        usuario_id=None, despues=resumen)
    return resumen


def main() -> None:
    with SessionLocal() as db:
        resumen = rotar(db, get_almacen())
        db.commit()
    print(f"Listo: {resumen['documentos_identidad']} documentos de identidad y {resumen['archivos']} archivos "
          "cifrados con la clave nueva. Ya puedes quitar la clave vieja de DATA_ENCRYPTION_KEY.")


if __name__ == "__main__":
    main()
