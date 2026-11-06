# Operación del día a día

Comandos desde la carpeta del proyecto en el servidor. `dc` = `docker compose -f docker-compose.prod.yml`
(puedes crear el atajo con `alias dc='docker compose -f docker-compose.prod.yml'`; con el demo público,
`alias dc='docker compose -f docker-compose.prod.yml -f docker-compose.demo.yml'`).

## Estado y logs

```bash
dc ps                                   # todo debe estar "healthy"
dc logs -f --tail 100 api               # los logs son JSON; cada línea trae "peticion"
dc logs api | grep '"peticion": "ID"'   # todo lo de una petición (el ID sale en la cabecera X-Request-ID)
curl -s https://panel.dragones.com/api/v1/salud/worker
```

## Copias de seguridad

- Corren solas cada día (`RESPALDO_HORA`, 03:30 por defecto) en el servicio `respaldo`.
- Quedan en el volumen `respaldos` (7 diarias, 4 semanales, 6 mensuales) y, si está configurado, en el almacenamiento
  externo (`RESPALDO_DESTINO`).
- Van cifradas con la clave **pública** de age: el servidor no puede leerlas. Para restaurar hace falta la **privada**,
  que vive en tu gestor de contraseñas.
- Una copia contiene: la base de datos completa (`pg_dump`) y los archivos subidos (documentos cifrados y fotos).
- **No** contiene el `.env`: guarda `DATA_ENCRYPTION_KEY`, `SECRET_KEY` y las demás claves aparte. Sin
  `DATA_ENCRYPTION_KEY`, los documentos de identidad de una copia no se pueden descifrar.

Copia manual (antes de actualizar o de un cambio grande):

```bash
dc exec respaldo respaldar.sh --ahora
dc exec respaldo ls -lh /respaldos/diario
```

## Restaurar una copia

1. Copia la clave privada al servidor solo mientras dura la restauración: `nano /tmp/clave-age.txt`.
2. Verifica la copia (no cambia nada):
   ```bash
   dc run --rm -v /tmp/clave-age.txt:/clave.txt:ro --entrypoint restaurar.sh respaldo \
       /respaldos/diario/dragones-AAAAMMDD-HHMM.tar.age /clave.txt
   ```
3. Restaura (reemplaza los datos actuales):
   ```bash
   dc stop api worker
   dc run --rm --user 10001 -e CONFIRMAR=si -v /tmp/clave-age.txt:/clave.txt:ro --entrypoint restaurar.sh respaldo \
       /respaldos/diario/dragones-AAAAMMDD-HHMM.tar.age /clave.txt
   dc up -d
   shred -u /tmp/clave-age.txt
   ```
   Para una copia que solo está fuera del servidor: `dc run --rm --entrypoint rclone respaldo copy remoto:dragones-respaldos/diario/<archivo> /respaldos/diario/`.

**Simulacro mensual**: restaura la última copia en una base aparte (`-e PGDATABASE=prueba_restauracion -e SOLO_BASE=si`,
creada antes con `dc exec db createdb -U dragones prueba_restauracion`) y compara conteos
(`select count(*) from alumnos`). Sin `SOLO_BASE=si` el script reemplaza también los archivos **reales** (el volumen
de documentos es el mismo). Al terminar: `dc exec db dropdb -U dragones prueba_restauracion`. Una
copia que nunca se restauró no es una copia.

## Rotar claves

**Clave de cifrado (`DATA_ENCRYPTION_KEY`)** — si se filtró o una vez al año:

```bash
# 1. Genera la nueva y ponla DELANTE de la vieja en .env:  DATA_ENCRYPTION_KEY={nueva},{vieja}
dc stop api worker
dc run --rm api python -m app.scripts.rotar_clave
# 2. Deja solo la nueva en .env:  DATA_ENCRYPTION_KEY={nueva}
dc up -d
dc exec respaldo respaldar.sh --ahora     # copia nueva ya cifrada con la clave nueva
```

Guarda la vieja hasta que las copias antiguas (hechas con ella) expiren (~6 meses).

**Clave de los tokens (`SECRET_KEY`)**: pon la actual en `SECRET_KEY_ANTERIOR`, una nueva en `SECRET_KEY`,
`dc up -d`; a los 15 minutos borra `SECRET_KEY_ANTERIOR` y `dc up -d`. Nadie pierde su sesión.

**Contraseña de la base** (`POSTGRES_PASSWORD`): `dc exec db psql -U dragones -c "ALTER USER dragones PASSWORD 'nueva'"`,
cámbiala en `.env` y `dc up -d`.

## Si algo falla

| Síntoma | Qué revisar |
|---|---|
| UptimeRobot avisa `/salud` caído | `dc ps` y `dc logs --tail 200 api db web` |
| `/salud/worker` en 503 | `dc logs --tail 200 worker`; `dc restart worker` |
| healthchecks.io avisa copia fallida | `dc logs --tail 100 respaldo` (espacio en disco: `df -h`) |
| El certificado no se renueva | El DNS debe apuntar al servidor y los puertos 80/443 abiertos; `dc logs web` |
| Disco lleno | `docker system df`; los logs ya rotan solos (5 × 10 MB por servicio) |

Ante un incidente con datos personales (acceso indebido, filtración): cambia las claves comprometidas, revisa la
auditoría (`select * from auditoria order by creado_en desc limit 200`) y, según la Ley 1581, informa a la SIC y a los
afectados.
