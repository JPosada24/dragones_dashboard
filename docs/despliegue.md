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

### Oracle Cloud gratis (Always Free)

Oracle regala una VM ARM de **2 OCPU y 12 GB** (de sobra para la plataforma), pero casi nunca hay cupo al crearla
desde la consola ("Out of host capacity"). `deploy/oracle/conseguir-vm.ps1` lo reintenta solo hasta conseguirla.

1. **CLI de Oracle** (PowerShell, una vez; acepta las opciones por defecto y abre otra terminal al terminar):
   ```powershell
   Set-ExecutionPolicy RemoteSigned -Scope CurrentUser
   powershell -NoProfile -ExecutionPolicy Bypass -Command "iex ((New-Object System.Net.WebClient).DownloadString('https://raw.githubusercontent.com/oracle/oci-cli/master/scripts/install/install.ps1'))"
   oci --version
   ```
2. **API key**: en la consola, ícono de perfil (arriba a la derecha) → *My profile* → *API keys* → *Add API key* →
   *Generate API key pair* → **Download private key** → *Add*. Guarda la llave descargada como
   `C:\Users\<tú>\.oci\oci_api_key.pem` y copia el texto que muestra Oracle (*Configuration file preview*) en
   `C:\Users\<tú>\.oci\config`, cambiando `key_file` por esa ruta. Prueba: `oci os ns get`. La `.pem` es una
   contraseña: no la compartas ni la subas a git.
3. **Correr el script** desde la carpeta del proyecto (usa `~\.ssh\id_ed25519.pub`; otra llave con `-ClavePublica`):
   ```powershell
   powershell -ExecutionPolicy Bypass -File deploy\oracle\conseguir-vm.ps1
   ```
   Pide la VM cada 60 s rotando las zonas de tu región; deja el PC encendido y sin suspender (puede tardar horas o
   días). Busca solo la imagen de Ubuntu 24.04 ARM y la subred (si no hay, crea la red) y abre los puertos 80 y 443
   en Oracle. Al lograrlo suena y muestra la IP. Si tras un día no entra, prueba `-Ocpus 1 -MemoriaGb 6` (también
   gratis y suele haber más cupo). Volver a correrlo no crea otra VM.
4. **Diferencias con la guía general** en el paso siguiente:
   - El usuario es `ubuntu` (`ssh ubuntu@IP`), ya con `sudo` y sin acceso por contraseña ni como root: salta el
     punto 3 (o créate tu usuario con `sudo`).
   - **No uses `ufw`**: las imágenes de Oracle traen su propio cortafuegos (iptables) que bloquea todo menos SSH.
     En lugar del punto 4 abre la web así:
     ```bash
     sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
     sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
     sudo netfilter-persistent save
     sudo apt update && sudo apt -y upgrade && sudo apt -y install unattended-upgrades fail2ban
     ```
   - Oracle puede **recuperar VMs gratuitas inactivas** (uso de CPU, red y memoria muy bajo durante 7 días). Pasar
     la cuenta a *Pay As You Go* lo evita y no cobra mientras no salgas de lo gratuito; activa una alerta de
     presupuesto en *Billing → Budgets* (por ejemplo USD 1) para enterarte si algo empieza a costar.
5. **Hacer el reintento sin tener el PC encendido** (repo público ⇒ minutos de Actions gratis): el mismo intento
     automático corre en GitHub Actions, `.github/workflows/conseguir-vm.yml` (el programa es
     `deploy/oracle/conseguir-vm.py`, traducción del `.ps1` a Python). Configuración única:
     - Crea los secretos en *Settings → Secrets and variables → Actions*: `OCI_CLI_USER`, `OCI_CLI_TENANCY`,
       `OCI_CLI_FINGERPRINT`, `OCI_CLI_REGION` (copia los valores de tu `~\.oci\config`) y `SSH_PUB_KEY`
       (el contenido de tu `~\.ssh\id_ed25519.pub`).
     - Para `OCI_CLI_KEY_CONTENT`, pega el texto completo de `~\.oci\oci_api_key.pem` (con sus líneas
       `BEGIN/END PRIVATE KEY`): es una contraseña, nunca la subas al repo ni la compartas.
     - Corre el workflow a mano una vez (*Actions → Conseguir VM Oracle → Run workflow*) sobre `'main'` para
       validar los secretos (debe salir verde, sin "PARO:"). El `schedule` del yml reintentaba solo
       cada 5 minutos: **quedó desactivado el 2026-11-06** cuando la VM ya encendió, para dejar de gastar
       ejecuciones; si algún día vuelve a faltar cupo, vuelve a añadir esa línea al `on:`.
     - Cuando consiga la VM, abre un **issue con la IP** en el repositorio (aviso por Telegram si defines los
       dos secretos `TELEGRAM_*`) y sigue en el punto 1.4 de esta guía con `ssh ubuntu@IP`.

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

1. **Cloudflare R2** (o Backblaze B2): crea un bucket `dragones-respaldos` y una llave de API («Object Read & Write»,
   solo ese bucket). Completa `RESPALDO_DESTINO=remoto:dragones-respaldos` y en el `.env`: `RCLONE_TIPO=s3`,
   `RCLONE_PROVEEDOR=Cloudflare`, `RCLONE_ENDPOINT=https://<id-de-cuenta>.r2.cloudflarestorage.com` y la llave
   (`RCLONE_ACCESS_KEY_ID`, `RCLONE_SECRET_ACCESS_KEY`). En el bucket, activa una regla de ciclo de vida que borre
   objetos de más de 200 días (el script solo agrega: no borra nada fuera del servidor).
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

## 7. Demo público (opcional)

Una copia del panel con un **club ficticio** (58 alumnos, seis semanas de asistencia, multas, una rifa y dos
torneos) en `demo.<dominio>`, para mostrarlo sin tocar nada real. Corre en el mismo servidor con **base de datos,
archivos y claves propios** (`docker-compose.demo.yml`): no ve los datos reales ni recibe los secretos de
producción. La pantalla de entrada muestra las cuentas de prueba (una por rol, clave pública `DemoDragones2026`);
en el demo no se pueden tocar las cuentas ni subir archivos, y todo se regenera cada día a las 04:00.

1. DNS: registro `A demo` → la IP del servidor (nube gris, igual que `panel`).
2. En el `.env` del servidor agrega (claves nuevas, **distintas** de las de producción):
   ```bash
   docker compose -f docker-compose.prod.yml run --rm --no-deps api python -c "import secrets; from cryptography.fernet import Fernet; print('DEMO_POSTGRES_PASSWORD=' + secrets.token_hex(24)); print('DEMO_SECRET_KEY=' + secrets.token_hex(32)); print('DEMO_DATA_ENCRYPTION_KEY=' + Fernet.generate_key().decode())" >> .env
   echo "DEMO_DOMINIO=demo.dragonesvolleyclub.com" >> .env
   ```
3. Arranca todo con **los dos archivos** (desde ahora, siempre así; si actualizas solo con el de producción, el
   sitio del demo se cae hasta el siguiente `up` con ambos):
   ```bash
   alias dc='docker compose -f docker-compose.prod.yml -f docker-compose.demo.yml'
   dc up -d --build
   dc logs -f demo-reinicio   # «Demo listo: 58 alumnos…» (tarda uno o dos minutos la primera vez)
   ```

Regenerarlo ya (por ejemplo después de una actualización): `dc exec demo-reinicio python -m app.scripts.demo`.
Quitarlo: `dc stop api-demo db-demo demo-reinicio` y vuelve a arrancar solo con `docker-compose.prod.yml`.

