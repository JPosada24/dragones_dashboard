#!/usr/bin/env bash
# Copia de seguridad diaria de Dragones. Corre en su propio contenedor (servicio "respaldo").
#
#   - Base de datos: pg_dump en formato "custom" (se restaura con pg_restore, tabla por tabla si hace falta).
#   - Archivos: el volumen de documentos (ya van cifrados con Fernet; aquí se vuelven a cifrar con age).
#   - Todo se cifra con la CLAVE PÚBLICA de age (RESPALDO_AGE_PUBLICA): el servidor puede crear copias pero
#     no leerlas. La clave privada la guarda el dueño fuera del servidor (gestor de contraseñas).
#   - Retención local: 7 diarias, 4 semanales (domingo), 6 mensuales (día 1).
#   - Fuera del servidor: si RESPALDO_DESTINO tiene un remoto de rclone (p. ej. "b2:dragones-respaldos"), se sincroniza.
#   - Aviso: si RESPALDO_PING_URL está (p. ej. healthchecks.io, gratis), se avisa el éxito o el fallo de cada copia.
#
# Uso:  respaldar.sh            -> espera a RESPALDO_HORA (03:30 por defecto, hora de Bogotá) y repite cada día
#       respaldar.sh --ahora    -> hace una copia ya y termina (para probar o antes de una actualización)
set -Eeuo pipefail

: "${PGHOST:=db}" "${PGUSER:?falta PGUSER}" "${PGPASSWORD:?falta PGPASSWORD}" "${PGDATABASE:?falta PGDATABASE}"
: "${RESPALDO_AGE_PUBLICA:?falta RESPALDO_AGE_PUBLICA (clave pública de age, empieza por age1...)}"
: "${RESPALDO_HORA:=03:30}" "${RESPALDO_DESTINO:=}" "${RESPALDO_PING_URL:=}"
export TZ="${TZ:-America/Bogota}" PGHOST PGUSER PGPASSWORD PGDATABASE

RAIZ=/respaldos
DOCUMENTOS=/data/documentos

log() { printf '%s %s\n' "$(date '+%F %T')" "$*"; }
avisar() {  # el aviso nunca hace fallar la copia
  if [[ -n "$RESPALDO_PING_URL" ]]; then
    curl -fsS -m 10 --retry 3 "$RESPALDO_PING_URL$1" >/dev/null || log "No se pudo avisar a RESPALDO_PING_URL"
  fi
}

rotar() {  # rotar <carpeta> <cuántas conservar>
  local carpeta="$1" conservar="$2"
  # Más nuevas primero (el nombre lleva la fecha AAAAMMDD-HHMM); se borran las que sobran.
  find "$carpeta" -maxdepth 1 -type f -name 'dragones-*.tar.age' -printf '%f\n' | sort -r \
    | tail -n +"$((conservar + 1))" | while read -r viejo; do rm -f -- "${carpeta:?}/$viejo"; done
}

copia() {
  local sello tmp
  sello="$(date '+%Y%m%d-%H%M')"
  tmp="$(mktemp -d)"
  # La ruta queda fija al crear el trap (la variable local ya no existe cuando se ejecuta) y el trap se quita solo.
  # shellcheck disable=SC2064
  trap "rm -rf -- '$tmp'; trap - RETURN" RETURN
  mkdir -p "$RAIZ/diario" "$RAIZ/semanal" "$RAIZ/mensual"

  log "Base de datos…"
  pg_dump --format=custom --no-owner --no-privileges --file="$tmp/base.dump"
  pg_restore --list "$tmp/base.dump" >/dev/null  # verifica que el volcado se pueda leer
  log "Archivos…"
  tar -C "$DOCUMENTOS" -cf "$tmp/documentos.tar" .

  tar -C "$tmp" -cf - base.dump documentos.tar | age -r "$RESPALDO_AGE_PUBLICA" -o "$RAIZ/diario/dragones-$sello.tar.age"
  log "Copia lista: diario/dragones-$sello.tar.age ($(du -h "$RAIZ/diario/dragones-$sello.tar.age" | cut -f1))"

  [[ "$(date +%u)" == "7" ]] && cp -- "$RAIZ/diario/dragones-$sello.tar.age" "$RAIZ/semanal/"
  [[ "$(date +%d)" == "01" ]] && cp -- "$RAIZ/diario/dragones-$sello.tar.age" "$RAIZ/mensual/"
  rotar "$RAIZ/diario" 7
  rotar "$RAIZ/semanal" 4
  rotar "$RAIZ/mensual" 6

  if [[ -n "$RESPALDO_DESTINO" ]]; then
    log "Copiando fuera del servidor ($RESPALDO_DESTINO)…"
    rclone sync "$RAIZ" "$RESPALDO_DESTINO" --checksum --quiet
  fi
}

ejecutar() {
  avisar "/start"
  if copia; then
    avisar ""
    log "Respaldo terminado."
  else
    avisar "/fail"
    log "ERROR: el respaldo falló."
    return 1
  fi
}

segundos_hasta() {  # segundos hasta la próxima HH:MM (hoy o mañana)
  local ahora objetivo
  ahora="$(date +%s)"
  objetivo="$(date -d "today $1" +%s)"
  (( objetivo <= ahora )) && objetivo="$(date -d "tomorrow $1" +%s)"
  echo $(( objetivo - ahora ))
}

if [[ "${1:-}" == "--ahora" ]]; then
  ejecutar
  exit $?
fi

log "Servicio de respaldo iniciado: cada día a las $RESPALDO_HORA ($TZ)."
while true; do
  espera="$(segundos_hasta "$RESPALDO_HORA")"
  log "Próxima copia en $(( espera / 3600 )) h $(( espera % 3600 / 60 )) min."
  sleep "$espera"
  ejecutar || true  # un fallo se avisa y se reintenta mañana; el servicio no se cae
done
