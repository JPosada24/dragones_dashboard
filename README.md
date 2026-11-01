# Dragones — Plataforma de gestión para un club de voleibol

[![CI](https://github.com/JPosada24/dragones_dashboard/actions/workflows/ci.yml/badge.svg)](https://github.com/JPosada24/dragones_dashboard/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688)
![Angular](https://img.shields.io/badge/Angular-22-dd0031)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791)
![Licencia](https://img.shields.io/badge/licencia-MIT-green)

*[Read in English](README.en.md)*

Sistema real para administrar un club deportivo en Colombia: alumnos y acudientes, inscripciones con abonos y
plazos, asistencia con multas automáticas, mora, rifas con sorteo verificable, torneos con clubes externos, avisos
por correo y WhatsApp, y un sitio público alimentado por la misma API. Reemplaza hojas de cálculo y mensajes sueltos
por un registro único, auditable y con permisos por rol. Los datos del repositorio y de las pruebas son inventados.

## Qué resuelve

| Necesidad del club | Cómo lo resuelve |
|---|---|
| Saber quién está inscrito y quién debe | Inscripción anual con valor y plazo configurables, **abonos parciales**, prórrogas con motivo y estados (pendiente → activo → a expulsar → expulsado) |
| Que nadie «acomode» los pagos | Pagos, prórrogas, actas y auditoría **de solo agregar**: un trigger de PostgreSQL impide editarlos o borrarlos; un error se corrige con una anulación que deja rastro |
| Proteger datos de menores (Ley 1581) | Documento de identidad y archivos **cifrados en reposo**, autorización de datos registrada por alumno, fotos sin metadatos, política publicada y **registro de solicitudes** con su plazo legal en días hábiles |
| Controlar la asistencia | Entrenamientos programados solos desde el horario (salta festivos de Colombia y torneos), planilla P/A/J y **cierre diario** que marca ausencias y genera multas |
| Deudas que se eternizan | **Mora automática** a los 3 meses (configurable), con aviso previo a la familia y confirmación del dueño |
| Rifas sin enredos | Un talonario por alumno, pago por abonos y **sorteo** solo entre talonarios pagados, con acta inmutable verificable por su huella SHA-256 |
| Organizar torneos | Inscripción de clubes externos (también desde el sitio público) con cupo y **lista de espera automática** |
| Avisar sin pagar mensajería | Correo automático, bandeja en la plataforma y **WhatsApp con un clic** desde el número del club (sin bots ni API de pago) |
| Saber cuánto entra y rendir cuentas | **Reportes** de ingresos por mes y concepto y exportación de movimientos a CSV para la contabilidad |
| Varios entrenadores | Roles y permisos verificados en el servidor; el entrenador asistente no hereda acceso total |

## Arquitectura

```mermaid
flowchart LR
    S[Sitio público<br/>Angular · Netlify] -->|/api/v1/publico<br/>sin credenciales| C
    U[Panel<br/>Angular 22] --> C[Caddy<br/>HTTPS · CSP]
    subgraph Servidor · Docker Compose
      C -->|/api| API[FastAPI<br/>rutas → servicios → modelos]
      API --> DB[(PostgreSQL 16)]
      API --> V[(Archivos<br/>cifrados)]
      W[Worker<br/>tareas idempotentes] --> DB
      R[Respaldo<br/>diario, cifrado con age] --> DB
      R --> V
    end
    R -->|rclone| X[(Almacenamiento<br/>externo)]
```

- **Backend:** FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2. Capas `api/v1` (rutas y permiso) → `services` (reglas
  de negocio y alcance) → `models`. Las rutas no tienen lógica.
- **Frontend:** Angular 22 *standalone*, señales, OnPush, sin zone.js. Los tipos salen del **contrato OpenAPI** de la
  API: si el backend cambia y el frontend no, el CI falla.
- **Worker:** tareas programadas idempotentes con *advisory locks* de PostgreSQL (cierre de asistencia, vencimientos,
  mora, programación de entrenamientos, avisos, correos con reintentos). Deja un latido que se monitorea.
- **Decisiones de diseño:** [`docs/decisiones/`](docs/decisiones/README.md), una por archivo (por qué cada cosa es
  como es).

## Seguridad

- **Autenticación:** Argon2id; access token JWT de 15 min solo en memoria; refresh token rotativo en cookie
  `HttpOnly` con **detección de reuso**; bloqueo por cuenta y límite por IP compartido entre procesos (en PostgreSQL).
  Cambiar la contraseña o el rol invalida los tokens al instante.
- **Autorización:** cada ruta declara su permiso y el servicio aplica el alcance; un recurso ajeno responde 404.
  Hay pruebas de **qué rol no puede** hacer cada cosa.
- **Datos sensibles:** cifrado Fernet con **índice ciego** para buscar sin descifrar; claves rotables
  (`MultiFernet`, script de rotación). Nada sensible en la auditoría ni en los logs.
- **Archivos:** validados por su contenido real; las fotos se vuelven a codificar (sin EXIF/GPS, con tope contra
  bombas de descompresión).
- **Borde:** Caddy con HTTPS automático, HSTS, CSP estricta (`script-src 'self'`) y API sin puertos públicos.
- **Cadena de suministro:** dependencias de Python fijadas **con hashes**, `pip-audit`, `npm audit`, Trivy sobre la
  imagen, gitleaks, Dependabot y un hook de pre-commit contra secretos.
- **Copias de seguridad:** diarias, cifradas con la clave **pública** de age (el servidor no puede leerlas) y con
  la restauración probada de punta a punta.

## Calidad

El CI ([`ci.yml`](.github/workflows/ci.yml)) debe pasar completo antes de mezclar:

| Backend | Frontend | Infraestructura |
|---|---|---|
| ruff · pytest contra PostgreSQL real · **cobertura ≥ 90 %** (líneas y ramas) · pip-audit · contrato OpenAPI al día | ESLint (strict + accesibilidad) · compilación · Vitest con **cobertura mínima** · npm audit · tipos generados al día | Trivy sobre la imagen · shellcheck · compose de producción válido · gitleaks |

Las pruebas construyen el esquema con las **migraciones reales** (así se prueban también los triggers) y las reglas
con hora usan un reloj simulado.

## Cómo correrlo (desarrollo)

Requisito: Docker Desktop.

```powershell
copy .env.example .env      # y cambia los valores marcados "CAMBIA"
docker compose up --build
```

- Panel: <http://localhost:4300> (ingresa con `SUPERADMIN_EMAIL` y su clave)
- Documentación interactiva de la API: <http://localhost:8000/api/docs>

Pruebas y verificaciones: ver [`CONTRIBUTING.md`](CONTRIBUTING.md).
Producción: [`docs/despliegue.md`](docs/despliegue.md) (primera vez) y [`docs/operacion.md`](docs/operacion.md)
(copias, restauración, rotación de claves, incidentes).

## Estructura

```
backend/
  app/core/       configuración, seguridad, cifrado, límites, observabilidad, almacenamiento
  app/models/     tablas (SQLAlchemy 2)
  app/schemas/    entradas y salidas (Pydantic v2) — de aquí sale el contrato OpenAPI
  app/services/   reglas de negocio
  app/api/v1/     rutas
  app/worker.py   tareas programadas
  alembic/        migraciones
  tests/          pruebas (PostgreSQL real)
frontend/         panel Angular 22 (tipos generados en src/app/core/api/)
deploy/           Caddyfile y servicio de copias de seguridad
docs/             despliegue, operación y decisiones de arquitectura
```

## Licencia

[MIT](LICENSE) © 2026 Julian Posada
