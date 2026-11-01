# Copias de seguridad diarias: base de datos + archivos, cifradas con age (clave pública) y, si se configura,
# copiadas fuera del servidor con rclone (Backblaze B2, Cloudflare R2, Google Drive…). Ver docs/operacion.md.
FROM alpine:3.20
RUN apk add --no-cache bash coreutils tzdata postgresql16-client age rclone curl \
    && adduser -D -u 10002 respaldo
COPY respaldar.sh restaurar.sh /usr/local/bin/
RUN chmod 0755 /usr/local/bin/respaldar.sh /usr/local/bin/restaurar.sh
USER respaldo
ENTRYPOINT ["/usr/local/bin/respaldar.sh"]
