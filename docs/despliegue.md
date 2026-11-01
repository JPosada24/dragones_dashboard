# Despliegue en producción (primera vez)

Guía paso a paso para poner la plataforma en un servidor propio (VPS). Tiempo estimado: 1 a 2 horas. Lo único que se
paga es el servidor (~USD 5/mes) y el dominio (~USD 10–15/año); todo lo demás es gratuito.

```
dragones.com            → Netlify (sitio público, proyecto aparte)
panel.dragones.com      → VPS: Caddy (HTTPS) + panel + API + worker + PostgreSQL + copias de seguridad
copias fuera del VPS    → Cloudflare R2 o Backblaze B2 (gratis hasta 10 GB)
```

## 0. Antes de empezar

Ten a mano, guardado en tu gestor de contraseñas (Bitwarden, 1Password…):

| Qué | Cómo se genera |
|---|---|
| `SECRET_KEY` | `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `DATA_ENCRYPTION_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `POSTGRES_PASSWORD` | `python -c "import secrets; print(secrets.token_hex(24))"` (solo letras y números) |
| Par de claves de respaldo | `docker run --rm alpine:3.20 sh -c "apk add -q age && age-keygen"` |
| Contraseña del primer SuperAdmin | 12+ caracteres con mayúscula, minúscula y número |

> **La `DATA_ENCRYPTION_KEY` y la clave privada de respaldo son irrecuperables.** Si se pierden, los documentos de
> identidad y las copias de seguridad no se pueden leer. Guárdalas en dos lugares.

## 1. El servidor

1. Crea una cuenta en el proveedor (por ejemplo Hetzner, DigitalOcean o Vultr) y un servidor **Ubuntu 24.04**,
   2 GB de RAM, en la región de Estados Unidos más cercana. Agrega tu **llave SSH** al crearlo (no uses contraseña).
2. Entra: `ssh root@IP_DEL_SERVIDOR`.
3. Crea un usuario propio y protege el acceso:
   ```bash
   adduser julian && usermod -aG sudo julian
   rsync --archive --chown=julian:julian ~/.ssh /home/julian
   sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/; s/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
   systemctl restart ssh
   ```
4. Cortafuegos y actualizaciones automáticas de seguridad:
   ```bash
   ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443 && ufw --force enable
   apt update && apt -y upgrade && apt -y install unattended-upgrades fail2ban
   ```
5. Instala Docker (script oficial) y entra de nuevo como tu usuario:
   ```bash
   curl -fsSL https://get.docker.com | sh && usermod -aG docker julian
   exit   # y vuelve a entrar:  ssh julian@IP_DEL_SERVIDOR
   ```

## 2. El dominio

En el panel DNS (recomendado: Cloudflare, gratis) crea un registro **A** `panel` → `IP_DEL_SERVIDOR`.
Si usas Cloudflare, déjalo en **"DNS only"** (nube gris) para que Caddy pueda sacar el certificado.

## 3. El código y la configuración

```bash
git clone https://github.com/JPosada24/dragones_dashboard.git dragones && cd dragones
cp .env.example .env && nano .env
```

Cambia como mínimo:

```ini
ENTORNO=produccion
COOKIE_SECURE=true
POSTGRES_PASSWORD=...           SECRET_KEY=...           DATA_ENCRYPTION_KEY=...
PANEL_DOMINIO=panel.dragones.com
ACME_EMAIL=correo-del-club@gmail.com
CORS_ORIGINS=https://panel.dragones.com
SITIO_ORIGENES=https://dragones.com
SITIO_URL=https://dragones.com
SUPERADMIN_EMAIL=...            SUPERADMIN_PASSWORD=...
RESPALDO_AGE_PUBLICA=age1...    # la PÚBLICA; la privada se queda en tu gestor de contraseñas
EMAIL_MODO=smtp                 # y los SMTP_* con la contraseña de aplicación de Gmail
```

Protege el archivo: `chmod 600 .env`.

## 4. Arrancar

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps        # todo "healthy" en 1–2 minutos
```

Abre `https://panel.dragones.com`, entra con el SuperAdmin y **cambia su contraseña**. Después borra
`SUPERADMIN_PASSWORD` del `.env` (ya no se usa).

En el sitio público (Netlify), pon `API_URL=https://panel.dragones.com` en las variables de entorno y vuelve a
publicar.

## 5. Copias fuera del servidor y monitoreo (15 minutos, gratis)

1. **Cloudflare R2** (o Backblaze B2): crea un bucket `dragones-respaldos` y una llave de API con acceso solo a ese
   bucket. Completa `RESPALDO_DESTINO=remoto:dragones-respaldos` y los `RCLONE_*` del `.env`. En el bucket, activa
   una regla de ciclo de vida que borre objetos de más de 200 días.
2. **healthchecks.io**: crea un chequeo diario y pega su URL en `RESPALDO_PING_URL`. Te escribe si una copia falla.
3. **UptimeRobot**: dos monitores HTTP cada 5 minutos: `https://panel.dragones.com/api/v1/salud` y
   `https://panel.dragones.com/api/v1/salud/worker`.
4. (Opcional) **GlitchTip** o **Sentry**: crea un proyecto y pega el DSN en `SENTRY_DSN`.

Aplica los cambios: `docker compose -f docker-compose.prod.yml up -d`.

Prueba la copia **hoy mismo** (no esperes a necesitarla):

```bash
docker compose -f docker-compose.prod.yml exec respaldo respaldar.sh --ahora
```

Y una vez al mes, practica la restauración (ver `docs/operacion.md`).

## 6. Actualizar a una versión nueva

```bash
cd ~/dragones
docker compose -f docker-compose.prod.yml exec respaldo respaldar.sh --ahora   # copia antes de actualizar
git pull
docker compose -f docker-compose.prod.yml up -d --build                       # aplica migraciones al arrancar
```

Si algo sale mal: `git checkout <versión anterior>` y vuelve a levantar; si la migración ya cambió datos, restaura
la copia que acabas de hacer.
