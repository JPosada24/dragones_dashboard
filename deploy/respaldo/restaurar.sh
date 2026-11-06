#!/usr/bin/env bash
# Restaura una copia de seguridad de Dragones (base de datos + archivos). DESTRUCTIVO: reemplaza los datos actuales.
#
# Uso (desde el servidor, con la API y el worker detenidos):
#   docker compose -f docker-compose.prod.yml stop api worker
#   docker compose -f docker-compose.prod.yml run --rm -v /ruta/a/clave-privada.txt:/clave.txt:ro \
#       --entrypoint restaurar.sh respaldo /respaldos/diario/dragones-AAAAMMDD-HHMM.tar.age /clave.txt
#   docker compose -f docker-compose.prod.yml up -d
#
# La clave privada de age NO vive en el servidor: se trae solo para restaurar y se borra después.
# Simulacro en una base aparte: -e PGDATABASE=prueba_restauracion -e SOLO_BASE=si (no toca los archivos reales).
set -Eeuo pipefail

archivo="${1:?Uso: restaurar.sh <copia.tar.age> <clave-privada-age>}"
clave="${2:?Falta la ruta de la clave privada de age}"
: "${PGHOST:=db}" "${PGUSER:?}" "${PGPASSWORD:?}" "${PGDATABASE:?}"
export PGHOST PGUSER PGPASSWORD PGDATABASE

tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT

echo "Descifrando $archivo…"
age -d -i "$clave" "$archivo" | tar -C "$tmp" -xf -
pg_restore --list "$tmp/base.dump" >/dev/null

if [[ "${CONFIRMAR:-}" != "si" ]]; then
  echo "La copia es válida. Para reemplazar los datos actuales vuelve a correrlo con -e CONFIRMAR=si"
  exit 0
fi

echo "Restaurando la base de datos…"
pg_restore --clean --if-exists --no-owner --no-privileges --single-transaction --dbname="$PGDATABASE" "$tmp/base.dump"
if [[ "${SOLO_BASE:-}" == "si" ]]; then
  echo "SOLO_BASE=si: los archivos no se tocan."
  echo "Listo."
  exit 0
fi
echo "Restaurando los archivos…"
find /data/documentos -mindepth 1 -delete
tar -C /data/documentos -xf "$tmp/documentos.tar"
echo "Listo. Arranca de nuevo la API y el worker."
