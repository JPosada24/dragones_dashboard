# Dragones — Plataforma de gestión del Club de Voleibol

Backend **FastAPI + PostgreSQL**, frontend **Angular** (próxima fase), todo con **Docker**.
La explicación completa del diseño está en el documento *"Dragones – Documento de diseño y desarrollo"*.

## Estado actual: Fase 1 (parte A) — cimientos

Ya incluye:

- Entorno Docker (PostgreSQL 16 + API) que arranca con un comando.
- Autenticación segura: contraseñas con Argon2id, access token JWT de 15 minutos y refresh token
  rotativo en cookie `HttpOnly` / `SameSite=Strict`, con detección de reutilización y bloqueo temporal
  tras 5 intentos fallidos.
- Roles y permisos (SuperAdmin, Admin, Entrenador, Miembro) verificados siempre en el servidor.
- Gestión de usuarios (solo SuperAdmin) y parámetros del club (multa $2.000, plazo 30 días,
  mora 3 meses, talonario de 20 puestos a $2.000, etc.).
- Bitácora de auditoría **de solo agregar** (un trigger de PostgreSQL impide editarla o borrarla).
- Migración inicial con Alembic y pruebas automatizadas.

## Fase 1 (parte B) — alumnos e inscripciones

- El Entrenador registra alumnos, acudientes, documentos e inscripciones de su rama; los menores requieren acudiente.
- Documento de identidad **cifrado en reposo** (Fernet) y enmascarado en las respuestas.
- Documentos del alumno (PDF/JPG/PNG, validados por contenido, cifrados en el volumen `documentos`).
- Inscripciones: valor y plazo de pago tomados de `configuracion` (por defecto $90.000 y 30 días),
  abonos parciales, prórrogas con motivo (solo Admin/SuperAdmin) y estados pendiente de pago → activo → a expulsar → expulsado / rechazado.

Siguiente: asistencia y multas (Fase 2), y luego el frontend Angular.

## Cómo arrancar (Windows / PowerShell)

Requisito: **Docker Desktop** abierto.

```powershell
cd C:\Users\Julian Posada\Desktop\Personal\Proyectos\Dashboard_DVC

# 1) Crear tu archivo de secretos
copy .env.example .env
notepad .env        # cambia POSTGRES_PASSWORD, SECRET_KEY, DATA_ENCRYPTION_KEY y SUPERADMIN_PASSWORD

# 2) Levantar todo (la primera vez construye la imagen)
docker compose up --build
```

Al arrancar, el contenedor `api` aplica las migraciones y crea los catálogos y el primer SuperAdmin
con lo que pusiste en `.env`. Luego abre:

- Documentación interactiva: <http://localhost:8000/api/docs>
- Salud: <http://localhost:8000/api/v1/salud>

Para generar una `SECRET_KEY` y una `DATA_ENCRYPTION_KEY` sin instalar Python:

```powershell
docker compose run --rm --no-deps api python -c "import secrets; print(secrets.token_urlsafe(48))"
docker compose run --rm --no-deps api python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

> **Guarda `DATA_ENCRYPTION_KEY` en un lugar seguro** (gestor de contraseñas). Si se pierde, los documentos de
> identidad y archivos cifrados no se pueden recuperar.

> Usa solo letras y números en `POSTGRES_PASSWORD` (va dentro de una URL).

## Pruebas

Se ejecutan dentro del contenedor, contra PostgreSQL real (crea una base `dragones_test` aparte;
no toca tus datos):

```powershell
docker compose run --rm --user root api sh -c "pip install -q -r requirements-dev.txt && pytest"
```

## Probar el login a mano

En <http://localhost:8000/api/docs>: `POST /api/v1/auth/login` con tu `SUPERADMIN_EMAIL` y su clave.
Copia el `access_token`, pulsa **Authorize** y pégalo. Con eso ya puedes probar `GET /api/v1/auth/me`,
`POST /api/v1/usuarios` y `GET /api/v1/configuracion`.

## Estructura

```
backend/
  app/
    core/        configuración, seguridad (Argon2, JWT) y catálogo de permisos
    db/          motor y sesión de base de datos
    models/      tablas (acceso, configuración, auditoría)
    schemas/     validación de entradas y salidas (Pydantic)
    services/    reglas de negocio
    api/v1/      rutas (auth, usuarios, configuración, salud)
    scripts/     siembra inicial (python -m app.scripts.seed)
  alembic/       migraciones
  tests/         pruebas automatizadas
docker-compose.yml   entorno de desarrollo
.env.example         plantilla de variables (copiar a .env)
```

## Seguridad: notas importantes

- **Nunca subas `.env` a git** (ya está en `.gitignore`).
- En producción: `ENTORNO=produccion`, `COOKIE_SECURE=true`, HTTPS delante (Caddy) y
  `FORWARDED_ALLOW_IPS` ajustado al proxy. Con `ENTORNO=produccion` la app se niega a arrancar con
  `COOKIE_SECURE=false` o con la `SECRET_KEY` de ejemplo, y la documentación interactiva se apaga.
- Las migraciones y la siembra del compose de desarrollo corren al arrancar; en producción se ejecutarán
  como un paso aparte del despliegue.
- Pendiente en próximas fases: límite de peticiones con Redis, cifrado del documento de identidad,
  CSRF adicional para el frontend, revisión de seguridad independiente antes de salir a producción.
