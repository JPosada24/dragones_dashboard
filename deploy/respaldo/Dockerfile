# Copias de seguridad diarias: base de datos + archivos, cifradas con age (clave pública) y, si se configura,
# copiadas fuera del servidor con rclone (Backblaze B2, Cloudflare R2, Google Drive…). Ver docs/operacion.md.
FROM alpine:3.20
# findutils: el find de BusyBox no tiene -printf (rotación de copias).
RUN apk add --no-cache bash coreutils findutils tzdata postgresql16-client age rclone curl \
    && adduser -D -u 10002 respaldo \
    && mkdir -p /respaldos && chown respaldo:respaldo /respaldos  # el volumen nuevo hereda este dueño
COPY respaldar.sh restaurar.sh /usr/local/bin/
RUN chmod 0755 /usr/local/bin/respaldar.sh /usr/local/bin/restaurar.sh
USER respaldo
ENTRYPOINT ["/usr/local/bin/respaldar.sh"]
