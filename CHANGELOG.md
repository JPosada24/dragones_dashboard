# Cambios

Formato: [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/). Versiones: [SemVer](https://semver.org/lang/es/).

## [Sin publicar]

### Añadido
- **Permisos por persona:** el SuperAdmin da o quita permisos a un Admin o Entrenador desde Usuarios (botón de
  ajustes), además de su rol; aplica sin cerrar su sesión y queda en la auditoría (migración 0027). Los permisos de
  cuentas no se le dan a nadie. La matriz «Roles y permisos» pasó de Configuración a Usuarios (`GET /usuarios/roles`).
- `deploy/oracle/conseguir-vm.ps1`: reintenta crear la VM gratuita de Oracle Cloud hasta que haya cupo (crea la red
  si falta y abre 80/443); sección «Oracle Cloud gratis» en `docs/despliegue.md`.

### Cambiado
- El rol **Admin** tiene todos los permisos menos administrar cuentas (antes no anulaba pagos, no confirmaba
  expulsiones ni cambiaba parámetros). Decisión 0013.
- Galería: las fotos suben de a 3 a la vez y se reducen en el navegador a 1920 px (lo que guarda el servidor)
  desde 800 KB: menos datos por la subida del internet de hogar.
- Copia fuera del servidor: `rclone copy` en vez de `sync` (la rotación local ya no borra la copia externa; la
  retención la pone el ciclo de vida del bucket) y `no_check_bucket` para llaves limitadas a un bucket (R2).

### Corregido
- CORS del sitio público: `/api/v1/publico` ya no responde `Access-Control-Allow-Credentials: true` al dominio del
  sitio (lo agregaba el CORS del panel). No era explotable (esas rutas no usan sesión), pero contradecía el diseño.
- Copias de seguridad: un paso fallido se anunciaba como «Copia lista» (bash ignora `set -e` dentro de
  `if función`); ahora la copia corre en un proceso aparte y el fallo se reporta (y se avisa a `RESPALDO_PING_URL`).
  Además, el volumen `/respaldos` pertenece al usuario del contenedor y se instaló `findutils` (rotación).
- `/api/v1/salud` y `/salud/worker` responden a `HEAD`: UptimeRobot revisa así y el 405 lo marcaba como caído.
- Simulacro de restauración: con `SOLO_BASE=si` restaura solo la base aparte; antes el simulacro documentado
  reemplazaba también los archivos reales.

## [0.4.0] - 2026-11-01

### Añadido
- **Reportes:** ingresos por mes y concepto (neto: las anulaciones restan) y descarga de movimientos en CSV para la
  contabilidad, protegida contra inyección de fórmulas y auditada (`reportes.ver`, `reportes.exportar`).
- **Nivel del alumno** (Iniciación / Avanzado) con filtro en la lista (migración 0025).
- **Solicitudes de datos personales** (Ley 1581): consultas y reclamos con plazo en días hábiles (sin festivos),
  prórroga única y alerta en el Resumen (migración 0026, `habeas.gestionar`).
- **Panel instalable** en el celular (PWA). El service worker solo guarda la aplicación, nunca datos de la API.
- **Producción:** `docker-compose.prod.yml`, Caddy con HTTPS y CSP estricta, copias diarias cifradas con age
  (restauración probada), limitador de intentos en PostgreSQL, latido del worker (`/salud/worker`), rotación de
  claves (cifrado y tokens), logs JSON con `X-Request-ID` y Sentry/GlitchTip opcional.
- Documentación: `docs/despliegue.md`, `docs/operacion.md`, decisiones de arquitectura, `CONTRIBUTING.md`,
  README en español e inglés.

### Quitado
- Permisos sin funcionalidad (`anio.cerrar`, `respaldo.exportar`); el catálogo ahora borra los permisos retirados.

### Calidad y operación
- La lógica de negocio sale de las rutas hacia los servicios (usuarios, club, configuración, notificaciones); errores de
  negocio uniformes en vez de `HTTPException`.
- Los vínculos de las cuentas se arman con un número fijo de consultas (antes, una por acudiente).
- Frontend: un solo manejo de acciones (`Operacion`) para las 10 pantallas que tenían su propia copia.
- Tipos del frontend generados del contrato OpenAPI; el CI falla si el contrato y los tipos se desalinean. La API
  publica los valores válidos (`Literal`) y una prueba verifica que coincidan con los `CHECK` de la base.
- Capa de acceso a datos (`AlumnosApi`, `AsistenciaApi`) y documentos del alumno en su propio componente.
- Dependencias de Python fijadas con hashes (`pip-compile`); Dependabot para pip, npm, Actions y Docker.
- CI: `pip-audit`, Trivy sobre la imagen de la API y cobertura mínima en backend y frontend.

## [0.3.0] - 2026-10-31

### Añadido
- Sitio público oficial conectado (proyecto aparte) con CORS restringido a `/publico` y sin credenciales.
- Galería por álbumes con portada propia, selección múltiple y subida con arrastrar y soltar; las fotos pesadas se
  reducen en el navegador.
- Equipo técnico con foto, «La formación va por rotaciones» editable y cifras públicas del club.
- Autorización de tratamiento de datos por alumno (Ley 1581) y política publicada en el sitio.
- Eliminar cuentas de usuario (solo SuperAdmin) conservando la evidencia de lo que registraron.
- Asistente de IA de solo consulta (apagado por defecto).

## [0.2.0] - 2026-10-30

### Añadido
- Panel completo: Resumen, Alumnos e inscripciones, Asistencia, Multas y mora, Rifas y sorteo, Torneos, Usuarios,
  Configuración y Avisos, con ayuda contextual en cada vista.
- Código del alumno (`F001`/`M001`), rifas sin compradores y sorteos repetibles con acta inmutable.
- Aviso de inasistencia sin motivo (casilla J).

## [0.1.0] - 2026-10-29

### Añadido
- Backend: autenticación (Argon2id, JWT de 15 min, refresh rotativo con detección de reuso), roles y permisos,
  auditoría de solo agregar, alumnos y acudientes con documento cifrado, inscripciones con abonos y prórrogas,
  asistencia con cierre diario y multas, mora, rifas, torneos y notificaciones.
- Worker de tareas periódicas idempotentes y programación automática de entrenamientos (festivos y torneos).

[0.4.0]: https://github.com/JPosada24/dragones_dashboard/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/JPosada24/dragones_dashboard/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/JPosada24/dragones_dashboard/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/JPosada24/dragones_dashboard/releases/tag/v0.1.0
