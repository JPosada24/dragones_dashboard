# Dragones — contexto del proyecto para Claude Code

Plataforma de gestión del **Club Deportivo Dragones (voleibol)**. Dueño y desarrollador: Julian Posada.
Responde siempre en **español**. Nombres de tablas, rutas y variables de negocio en español (como ya está).

## Stack (fijo)
- Backend: **FastAPI + SQLAlchemy 2 (síncrono) + Alembic + Pydantic v2**, PostgreSQL 16.
- Frontend: **Angular** (componentes standalone) — aún no creado.
- Todo en **Docker Compose**. El PC de desarrollo es **Windows** (comandos en PowerShell).
- Agente de IA (API de Claude) y Redis/worker llegan en fases posteriores.

## Decisiones de negocio (ya acordadas)
- Deporte: voleibol. **Solo dos ramas: masculina y femenina** (no hay categorías).
- Multa por inasistencia: **$2.000 COP**, se genera al cierre del día (11:59 pm) si no marcó ni justificó.
- Inscripción: pago máximo a **30 días**; solo Admin/SuperAdmin concede prórroga (con motivo, queda en auditoría).
  Valor $90.000 (configurable). **Se aceptan abonos parciales**; activa al completar el valor dentro del plazo.
  Abonos los registran Admin, SuperAdmin o Entrenador (solo su rama). Un abono errado no se borra: el
  SuperAdmin lo **anula** con motivo (movimiento negativo que lo revierte).
- **La inscripción la hace el Entrenador** (alumno, acudiente, documentos e inscripción, solo de su rama).
  Ningún alumno/acudiente (Miembro) se inscribe ni sube documentos por su cuenta: solo consulta lo suyo.
- Mora: **3 meses** → "A expulsar"; confirmación del SuperAdmin por defecto (configurable).
- Rifas: 4 por año; **1 talonario por alumno por rifa, 20 puestos × $2.000 = $40.000**. Cada puesto guarda comprador,
  teléfono y monto. Paz y salvo = talonario pagado al 100 %. El sorteo solo incluye talonarios pagados; guarda acta inmutable.
- Torneos: cupo por rama y por evento (sugerido 18 equipos), configurable.
- Notificaciones: **WhatsApp y correo**, detrás de una interfaz para poder cambiar de proveedor.
- Roles: SuperAdmin, Admin, Entrenador, Miembro (alumno mayor de edad o acudiente). Permisos en BD, verificados SIEMPRE en el servidor.
- **El dueño del club es el entrenador principal y responsable de todo**: usa el rol **SuperAdmin** (acceso total,
  incluidas las tareas de entrenador). El rol Entrenador queda para entrenadores asistentes, limitado a su rama.
  No ampliar el rol Entrenador para "dar todo": un asistente nuevo heredaría acceso total.
- Los datos del prototipo HTML (138 alumnos, nombres, cifras) son solo ejemplo de diseño.
- Todo valor "configurable" vive en la tabla `configuracion` (lo cambia solo el SuperAdmin).

## Estado
- HECHO (Fase 1 parte A): Docker, auth (Argon2id, JWT 15 min, refresh rotativo en cookie HttpOnly con detección de reuso,
  bloqueo tras 5 intentos), roles/permisos, usuarios, configuración, auditoría append-only (trigger), migración 0001, tests.
- HECHO (Fase 0, 2026-10-22): verificado en Docker. Migración 0001 + siembra OK, `/api/v1/salud` → ok,
  `alembic check` sin diferencias modelo↔migración, **26 pruebas en verde**. Correcciones:
  `tests/conftest.py` (el `import app.models` pisaba la variable `app` → TestClient recibía un módulo);
  las pruebas ahora construyen el esquema con `alembic upgrade head` (prueban migraciones y triggers);
  prueba nueva del trigger append-only de `auditoria`; `docker-compose.yml` ahora respeta `API_PORT`.
- Notas: si cambias `POSTGRES_PASSWORD` con el volumen ya creado, hay que `docker compose down -v`
  (Postgres solo usa la clave al inicializar). `ruff` aún no tiene configuración en el proyecto.
- HECHO (Fase 1 parte B, 2026-10-22): migración 0002 (alumnos, acudientes, alumno_acudiente, documentos_alumno,
  inscripciones, prorrogas + `usuarios.rama`) 0003 (abonos) y 0004 (anulación de abonos). **89 pruebas en verde** (incluye `tests/test_seguridad.py`), `alembic check` limpio.
  - Documento de identidad cifrado con Fernet (`DATA_ENCRYPTION_KEY` en `.env`; si se pierde, no se recupera) +
    índice ciego HMAC para buscar/evitar duplicados. Respuestas enmascaradas (`****1234`); el completo solo en
    `GET /alumnos/{id}/documento-identidad` (Admin/SA, auditado). Nunca en claro en la auditoría.
  - Archivos: solo PDF/JPG/PNG validados por firma, cifrados, en el volumen `documentos` (`core/almacen.py`,
    interfaz lista para S3). Suben/borran quienes tienen `alumnos.editar` (Entrenador solo su rama); el Miembro
    dueño solo los ve/descarga.
  - Inscripción: valor ($90.000) y plazo (30 días) leídos de `configuracion` al inscribir y guardados en la fila.
    Abonos en `pagos_inscripcion` (migración 0003, append-only); `monto_pagado` = suma, `fecha_pago` = fecha en que
    se completó; abono > saldo → 422. Abono tras el límite → 422 con mensaje claro. Valor 0 → activa de inmediato.
    Registrar abonos (`POST /inscripciones/{id}/pagos`) exige `inscripciones.abonar` (Admin, SA y Entrenador de la rama;
    `pagos.registrar` queda solo para Admin/SA: multas y rifas no las cobra el Entrenador salvo que se decida).
    Anular (`POST /inscripciones/{id}/pagos/{pago_id}/anular`, `pagos.anular` = solo SA, motivo ≥10, migración 0004):
    fila con monto negativo y `anula_id`; si la inscripción activa queda con saldo, vuelve a pendiente_pago. No se
    anula una anulación ni un abono dos veces; no se anula en a_expulsar/expulsado. Prórroga (`prorroga.conceder`, motivo ≥10, tabla append-only)
    amplía el plazo y reactiva una rechazada **por vencimiento** (no una rechazada a mano).
  - Estados: pendiente_pago →(pago) activo; pendiente_pago → rechazado; activo ⇄ a_expulsar; a_expulsar → expulsado
    (solo `expulsion.confirmar` = SuperAdmin). Una sola inscripción vigente por alumno y año (índice parcial).
  - `POST /inscripciones/vencer` rechaza pendientes vencidas (manual hasta que exista el worker diario).
  - Menor (edad < `edad_mayoria`, configurable) necesita acudiente al crear, editar, desvincular e inscribir.
  - Visibilidad: Admin/SA todo; Entrenador solo su `rama` (sin rama no ve ni registra nada; no puede crear ni
    mover alumnos a otra rama; inscribe solo con fecha de hoy); Miembro solo él mismo o sus hijos
    (vía `acudientes.usuario_id`). Errores de negocio: `services/errores.py` → HTTP en `main.py`.
  - Parámetros nuevos en `configuracion`: `valor_inscripcion`, `edad_mayoria`, `documento_max_mb`.
- SIGUIENTE: asistencia y multas (Fase 2). Pendiente de 1B para el frontend/worker: llamar a `vencer` a diario.
- Después: asistencia y multas → rifas/pagos/eventos → notificaciones y mora → frontend Angular, club público, IA, producción.

## Seguridad (obligatorio en todo código nuevo)
- Autorización en el servidor en cada ruta (`requiere`/`requiere_alguno`) **y** alcance en el servicio (rama/propios);
  recurso ajeno → 404 (no revelar que existe). Esquemas de entrada con `extra="forbid"`.
- Sin SQL armado con texto del usuario; búsquedas con `icontains(..., autoescape=True)`.
- Datos sensibles cifrados (`core/cifrado.py`) y nunca en claro en la auditoría ni en logs.
- Tablas de evidencia (auditoría, prórrogas, abonos) append-only con trigger `solo_agregar()`; correcciones con
  movimientos nuevos, nunca UPDATE/DELETE.
- Límites anti-abuso (`core/limites.py`): `MAX_CUERPO_MB` (413) y `LOGIN_FALLOS_POR_IP` por ventana (429), además
  del bloqueo por cuenta. El limitador vive en memoria: pasarlo a Redis cuando llegue el worker.
- Archivos: validar contenido real (firma), tamaño, nombre saneado, servir como `attachment` + `no-store`.
- Cada regla nueva lleva su prueba, incluidas las de permisos (qué rol NO puede).

## Convenciones
- Capas: `api/v1` (rutas) → `services` (reglas de negocio) → `models`. Validación en `schemas`.
- Dinero como enteros en pesos. Fechas con zona horaria (America/Bogota para reglas de negocio).
- Toda acción sensible llama a `services/auditoria.registrar`. La tabla `auditoria` no se edita ni se borra.
- Cada ruta declara su permiso con `Depends(requiere("..."))`. Nunca confiar en el frontend para autorizar.
- Cambios de esquema = nueva migración Alembic (no editar la 0001 ya aplicada).
- Secretos solo en `.env` (no se sube a git).
- Julian prefiere recibir los cambios como archivos concretos, no como .zip.

## Comandos (PowerShell, en la raíz del proyecto)
```
copy .env.example .env          # una vez; luego editar valores
docker compose up --build
docker compose run --rm --user root api sh -c "pip install -q -r requirements-dev.txt && pytest"
```
Si el puerto 8000 está ocupado: `API_PORT=8001` en `.env`.

## Documentación de diseño
Documento completo "Dragones – Documento de diseño y desarrollo" (modelo de datos, roles, reglas, API, seguridad, IA, fases).
