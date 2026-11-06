# Dragones — contexto del proyecto para Claude Code

Plataforma de gestión del **Club Deportivo Dragones (voleibol)**. Dueño y desarrollador: Julian Posada.
Responde siempre en **español**. Nombres de tablas, rutas y variables de negocio en español (como ya está).

## Stack (fijo)
- Backend: **FastAPI + SQLAlchemy 2 (síncrono) + Alembic + Pydantic v2**, PostgreSQL 16.
- Frontend: **Angular 22** (standalone, signals, OnPush, sin zone.js, Vitest) en `frontend/`. Diseño del prototipo
  `Dashboard Dragones (standalone).html` (oscuro, naranja #f2691e / oro #f5b731, Sora + Public Sans + IBM Plex Mono,
  Material Symbols; fuentes servidas localmente). Adaptaciones: Categoría→Rama, 20 puestos, Eventos→Torneos.
- Todo en **Docker Compose**. El PC de desarrollo es **Windows** (comandos en PowerShell).
- Agente de IA: API de Claude (SDK `anthropic`), solo consulta. Sin Redis: el limitador y los locks viven en PostgreSQL.

## Decisiones de negocio (ya acordadas)
- Deporte: voleibol. **Solo dos ramas: masculina y femenina** (no hay categorías).
- **Entrenamiento general** (ambas ramas juntas), programado **automáticamente** desde el horario semanal
  (hoy: lunes, miércoles y sábado; editable). Solo se cancela por **festivo** (Colombia), **torneo** u otro evento
  del club (a mano, con motivo). Sesiones extra a mano para reponer.
- Multa por inasistencia: **$2.000 COP**, se genera al cierre del día (11:59 pm) si no marcó ni justificó.
- Inscripción: pago máximo a **30 días**; solo Admin/SuperAdmin concede prórroga (con motivo, queda en auditoría).
  Valor $90.000 (configurable). **Se aceptan abonos parciales**; activa al completar el valor dentro del plazo.
  Abonos los registran Admin, SuperAdmin o Entrenador. Un abono errado no se borra: el
  SuperAdmin lo **anula** con motivo (movimiento negativo que lo revierte).
- **La inscripción la hace el Entrenador** (alumno, acudiente, documentos e inscripción).
  Ningún alumno/acudiente (Miembro) se inscribe ni sube documentos por su cuenta: solo consulta lo suyo.
- **No hay mensualidad.** Mora = **cualquier deuda sin pagar** (multas, talonarios) con **3 meses** → "A expulsar";
  confirmación del SuperAdmin por defecto (`expulsion_automatica` la hace directa). La inscripción no cuenta
  (tiene su propio plazo y vencimiento).
- **Código del alumno**: `F001…` (femenina) / `M001…` (masculina), consecutivo por rama, lo asigna el sistema al
  crear y nunca se reutiliza; si se corrige la rama recibe uno nuevo de la otra. Cada talonario guarda el código
  con el que se entregó. La boleta se lee **código-número** (`F012-07` = boleta 7 del talonario de F012).
- Rifas: 4 por año; **1 talonario por alumno por rifa, 20 boletas × $2.000 = $40.000**. **Sin compradores**: el
  talonario es del alumno y se paga completo o por abonos (`pagos_talonario`). Paz y salvo = talonario pagado al
  100 %. El sorteo solo incluye talonarios pagados, **se puede jugar varias veces** (una boleta no gana dos veces) y
  cada jugada deja un acta inmutable. Una rifa se puede **eliminar** (desaparece y deja de contar; su dinero y actas
  se conservan; con pagos o sorteos solo el SuperAdmin).
- **Inasistencia: basta con avisar** (sin motivo). Aviso antes del entrenamiento = justificado automático; aviso
  tardío lo revisa el staff.
- **Cancelar y anular no exigen motivo** (sesiones, rifas, torneos, multas, abonos y pagos): es opcional; quién y
  cuándo queda igual en la auditoría. Siguen pidiendo motivo: prórroga, cambio de estado de la inscripción,
  corrección de asistencia y rechazo de justificación.
- Torneos: los organiza el club y se inscriben **clubes externos** (no jugadores); cada equipo paga inscripción
  (valor fijado en cada torneo). Cupo por torneo (sugerido 18, `cupo_equipos_sugerido`). No hay otros eventos.
- Notificaciones: **sin costo**. Correo automático (Gmail con contraseña de aplicación) + bandeja en la plataforma;
  WhatsApp **manual** con enlaces wa.me que el staff envía desde el número del club (no se paga la API de Meta;
  NUNCA usar bots no oficiales de WhatsApp Web: arriesgan el bloqueo del número). Interfaz lista para otro proveedor.
- Roles: SuperAdmin, Admin, Entrenador, Miembro (alumno mayor de edad o acudiente). Permisos en BD, verificados SIEMPRE en el servidor.
- **El dueño del club es el entrenador principal y responsable de todo**: usa el rol **SuperAdmin** (acceso total,
  incluidas las tareas de entrenador). El rol Entrenador queda para entrenadores asistentes y es **general (ambas
  ramas; los usuarios no tienen rama)**, pero sin cobrar multas ni rifas, sin ver el documento completo
  (`alumnos.ver_documento`, solo Admin/SA), sin prórrogas ni horario. No ampliar el rol Entrenador para "dar todo":
  un asistente nuevo heredaría acceso total; si una persona necesita más, se le da a ella (permisos por persona).
- **Admin = todo menos administrar cuentas** (`usuarios.*`). El SuperAdmin da o quita permisos a cada Admin o
  Entrenador desde Usuarios (`usuarios_permisos`, 0027; efectivos = rol + dados − quitados en
  `Usuario.permisos_codigos`). Los de cuentas no se le dan a nadie. Cambiar el rol borra los ajustes. Decisión 0013.
- Los datos del prototipo HTML (138 alumnos, nombres, cifras) son solo ejemplo de diseño.
- Todo valor "configurable" vive en la tabla `configuracion` (lo cambia solo el SuperAdmin).

## Estado
El historial está en `CHANGELOG.md` y el porqué de cada decisión en `docs/decisiones/`; aquí solo lo que hay que
saber para seguir trabajando.

- **Hecho (v0.4.0):** backend con todas las reglas del club, panel completo, sitio público (proyecto aparte), asistente
  de IA (apagado sin `ANTHROPIC_API_KEY`), habeas data (autorización por alumno y registro de solicitudes con plazos
  en días hábiles, `services/habeas.py`), reportes de ingresos y CSV (`services/reportes.py`), nivel del alumno
  (Iniciación/Avanzado), panel instalable (PWA: el service worker no guarda datos de la API) y preparación para
  producción. Migraciones hasta la **0030**. Cobertura del backend ≥ 90 % (líneas y ramas) y umbrales del frontend en `angular.json`; el CI los exige.
- **Panel (frontend):** secciones en `core/secciones.ts`, pantallas en `paginas/<seccion>/` registradas en `PANTALLAS`
  de `app.routes.ts`, ayuda de cada vista en `core/ayudas.ts`, pestañas en `compartido/pestanas.ts`, tutorial guiado en
  `core/tutorial.service.ts` (pasos) + `layout/tutorial/` (resalta `data-tutorial="…"`) con el dragón
  `compartido/dragon.ts`. Todas las
  pantallas usan `compartido/operacion.ts` (`Operacion`: ocupado, mensaje, errorDialogo, abrir, ejecutar, exito,
  error; el error de un popup queda en el popup). Popups `compartido/dialogo.ts`, mensajes `<app-aviso>`, archivos
  `<app-zona-archivos>` (arrastrar y soltar) y `compartido/reducir-imagen.ts`. Acceso a datos en `*.api.ts` por
  pantalla (`AlumnosApi`, `AsistenciaApi`; seguir el patrón en las demás al tocarlas).
- **Contrato API → tipos:** los modelos del frontend son `Esquema<'XxxOut'>` (`core/api/tipos.ts`), generados.
  Tras cambiar rutas o esquemas, **desde Bash** (PowerShell 5 altera la codificación al redirigir):
  `docker compose exec -T api python -m app.scripts.openapi > frontend/openapi/openapi.json` y en `frontend/`
  `npm run api:tipos`. `tests/test_contrato.py` y el CI lo verifican. Los valores válidos son `Literal` en
  `schemas/comunes.py` (`tests/test_dominio.py` los compara con los CHECK de la base).
- **Backend:** rutas delgadas; la lógica va en `services/` (`club_panel.py` = panel del sitio). Errores de negocio
  con `services/errores.py`, nunca `HTTPException` en servicios.
- **Sitio público:** proyecto `DVC_CLAUDE` (git local sin remoto; commits con autor Julian Posada). Lee
  `/api/v1/publico/*` (CorsSitio, sin credenciales). Su política de datos (`public/politica-de-datos.html`) tiene
  campos `[POR COMPLETAR]` que llenará Julian.
- **Datos personales:** autorización de datos obligatoria al dar de alta un alumno (0022); eliminar un usuario lo
  anonimiza sin borrar la fila (0023).
- **Producción:** `docker-compose.prod.yml` + `deploy/Caddyfile` (HTTPS, CSP estricta; por eso el build no inyecta
  CSS crítico en línea) + `deploy/respaldo/` (copias diarias cifradas con age; fuera del servidor en Cloudflare R2 con `rclone copy`; restauración desde
  R2 probada el 2026-11-06).
  Limitador de intentos en Postgres (`intentos`, 0024) y latido del worker (`latidos`) → `/api/v1/salud/worker`.
  Claves rotables: `DATA_ENCRYPTION_KEY` admite varias (`app.scripts.rotar_clave`) y `SECRET_KEY_ANTERIOR`.
  Observabilidad en `core/observabilidad.py` (X-Request-ID, logs JSON en producción, `SENTRY_DSN` opcional sin datos
  personales). Guías: `docs/despliegue.md` y `docs/operacion.md`. Desplegado en OVHcloud VPS-2 (Canadá): `panel.dragonesvolleyclub.com`; sitio en Netlify (`dragonesvolleyclub.com`, repo `dvc-website`).
- **Dependencias:** Python en `requirements*.in`, fijadas con hashes con `pip-compile` (comando en
  `CONTRIBUTING.md`); npm con versiones exactas. Tras cambiar `package.json`, el contenedor del frontend tiene su
  propio `node_modules`: `docker compose exec frontend npm install`.
- **Pruebas:** nunca dos suites a la vez (comparten la base `dragones_test` y se vacían las tablas entre pruebas).
  Fixtures en `tests/conftest.py`, acciones en `tests/fabrica.py`; nunca importar de otro `test_*.py`.
- **Decidido:** el nivel (Iniciación/Avanzado) es solo un dato del alumno y un filtro. **No** se separan
  entrenamientos, asistencia ni multas por nivel: ambos niveles entrenan el mismo día y el entrenador marca esa
  sesión. La política de datos del sitio (`[POR COMPLETAR]`) la completa Julian.
- **Pendiente:** monitoreo (UptimeRobot, healthchecks.io, Sentry), correo real (Gmail),
  `SECURITY.md` y cerrar `filtro_acudientes_visibles` para quien no es staff.

## Seguridad (obligatorio en todo código nuevo)
- Autorización en el servidor en cada ruta (`requiere`/`requiere_alguno`) **y** alcance en el servicio (rama/propios);
  recurso ajeno → 404 (no revelar que existe). Esquemas de entrada con `extra="forbid"`.
- Sin SQL armado con texto del usuario; búsquedas con `icontains(..., autoescape=True)`.
- Datos sensibles cifrados (`core/cifrado.py`) y nunca en claro en la auditoría ni en logs.
- Tablas de evidencia (auditoría, prórrogas, abonos) append-only con trigger `solo_agregar()`; correcciones con
  movimientos nuevos, nunca UPDATE/DELETE.
- Límites anti-abuso (`core/limites.py`): `MAX_CUERPO_MB` (413) y `LOGIN_FALLOS_POR_IP` por ventana (429), además
  del bloqueo por cuenta. El limitador vive en PostgreSQL (compartido entre procesos; guarda el SHA-256 de la IP).
- Archivos: validar contenido real (firma), tamaño, nombre saneado, servir como `attachment` + `no-store`.
- Cada regla nueva lleva su prueba, incluidas las de permisos (qué rol NO puede).

## Convenciones
- Capas: `api/v1` (rutas) → `services` (reglas de negocio) → `models`. Validación en `schemas`.
- Dinero como enteros en pesos. Fechas con zona horaria (America/Bogota para reglas de negocio).
- Toda acción sensible llama a `services/auditoria.registrar`. La tabla `auditoria` no se edita ni se borra.
- Cada ruta declara su permiso con `Depends(requiere("..."))`. Nunca confiar en el frontend para autorizar.
- Cambios de esquema = nueva migración Alembic (no editar la 0001 ya aplicada).
- Secretos solo en `.env` (no se sube a git).
- Repositorio git (rama `main`). Mensajes con Conventional Commits en español (`feat:`, `fix:`, `refactor:`…) y
  versiones con etiqueta anotada + `CHANGELOG.md` (ver `CONTRIBUTING.md`). Antes de cada commit verificar que no se
  cuelen secretos (`.env`, claves).
- Remoto **público** (portafolio): https://github.com/JPosada24/dragones_dashboard. Todo lo que se commitea es
  público: nunca datos reales del club. Barreras: hook `.githooks/pre-commit` (activar con
  `git config core.hooksPath .githooks`), job gitleaks en `.github/workflows/ci.yml` (+ `.gitleaks.toml`, solo
  excepciones para marcadores de ejemplo) y push protection de GitHub. El push lo hace Julian (sin permiso aquí).
- Julian prefiere recibir los cambios como archivos concretos, no como .zip.

## Frontend (convenciones)
- Pantallas en `src/app/paginas/<seccion>/`, perezosas (`loadComponent`); al construir una, reemplazar
  `enConstruccion` en `app.routes.ts`. Nuevas secciones = una entrada en `core/secciones.ts`.
- Usar los tokens de `styles.scss` (nunca colores sueltos) y textos en español. Accesible: `<button>`/`<a>`
  reales, `aria-*`, foco visible. Nunca `innerHTML` con datos de la API.
- Token solo en memoria (nunca localStorage). La autorización real es del servidor.

## Comandos (PowerShell, en la raíz del proyecto)
```
copy .env.example .env          # una vez; luego editar valores
docker compose up --build
docker compose run --rm --user root api sh -c "pip install -q --require-hashes -r requirements-dev.txt && pytest --cov=app"
docker compose exec frontend npx ng test --watch=false --coverage   # pruebas del frontend
cd frontend; npm run lint                                    # ESLint (requiere npm ci en el PC)
docker compose run --rm --user root api sh -c "pip install -q ruff && ruff check ."
```
Si el puerto 8000 está ocupado: `API_PORT=8001` en `.env`.

## Documentación de diseño
Documento completo "Dragones – Documento de diseño y desarrollo" (modelo de datos, roles, reglas, API, seguridad, IA, fases).
