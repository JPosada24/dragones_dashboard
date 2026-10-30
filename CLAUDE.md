# Dragones — contexto del proyecto para Claude Code

Plataforma de gestión del **Club Deportivo Dragones (voleibol)**. Dueño y desarrollador: Julian Posada.
Responde siempre en **español**. Nombres de tablas, rutas y variables de negocio en español (como ya está).

## Stack (fijo)
- Backend: **FastAPI + SQLAlchemy 2 (síncrono) + Alembic + Pydantic v2**, PostgreSQL 16.
- Frontend: **Angular 22** (standalone, signals, OnPush, sin zone.js, Vitest) en `frontend/`. Diseño del prototipo
  `Dashboard Dragones (standalone).html` (oscuro, naranja #f2691e / oro #f5b731, Sora + Public Sans + IBM Plex Mono,
  Material Symbols; fuentes servidas localmente). Adaptaciones: Categoría→Rama, 20 puestos, Eventos→Torneos.
- Todo en **Docker Compose**. El PC de desarrollo es **Windows** (comandos en PowerShell).
- Agente de IA (API de Claude) y Redis/worker llegan en fases posteriores.

## Decisiones de negocio (ya acordadas)
- Deporte: voleibol. **Solo dos ramas: masculina y femenina** (no hay categorías).
- **Entrenamiento general** (ambas ramas juntas), programado **automáticamente** desde el horario semanal
  (hoy: lunes, miércoles y sábado; editable). Solo se cancela por **festivo** (Colombia), **torneo** u otro evento
  del club (a mano, con motivo). Sesiones extra a mano para reponer.
- Multa por inasistencia: **$2.000 COP**, se genera al cierre del día (11:59 pm) si no marcó ni justificó.
- Inscripción: pago máximo a **30 días**; solo Admin/SuperAdmin concede prórroga (con motivo, queda en auditoría).
  Valor $90.000 (configurable). **Se aceptan abonos parciales**; activa al completar el valor dentro del plazo.
  Abonos los registran Admin, SuperAdmin o Entrenador (solo su rama). Un abono errado no se borra: el
  SuperAdmin lo **anula** con motivo (movimiento negativo que lo revierte).
- **La inscripción la hace el Entrenador** (alumno, acudiente, documentos e inscripción, solo de su rama).
  Ningún alumno/acudiente (Miembro) se inscribe ni sube documentos por su cuenta: solo consulta lo suyo.
- **No hay mensualidad.** Mora = **cualquier deuda sin pagar** (multas, talonarios) con **3 meses** → "A expulsar";
  confirmación del SuperAdmin por defecto (`expulsion_automatica` la hace directa). La inscripción no cuenta
  (tiene su propio plazo y vencimiento).
- **Código del alumno**: `F001…` (femenina) / `M001…` (masculina), consecutivo por rama, lo asigna el sistema al
  crear y nunca se reutiliza; si se corrige la rama recibe uno nuevo de la otra. Cada talonario guarda el código
  con el que se entregó. La boleta se lee **código-número** (`F012-07` = boleta 7 del talonario de F012).
- Rifas: 4 por año; **1 talonario por alumno por rifa, 20 puestos × $2.000 = $40.000**. Cada puesto guarda comprador,
  teléfono y monto. Paz y salvo = talonario pagado al 100 %. El sorteo solo incluye talonarios pagados; guarda acta inmutable.
- Torneos: los organiza el club y se inscriben **clubes externos** (no jugadores); cada equipo paga inscripción
  (valor fijado en cada torneo). Cupo por torneo (sugerido 18, `cupo_equipos_sugerido`). No hay otros eventos.
- Notificaciones: **sin costo**. Correo automático (Gmail con contraseña de aplicación) + bandeja en la plataforma;
  WhatsApp **manual** con enlaces wa.me que el staff envía desde el número del club (no se paga la API de Meta;
  NUNCA usar bots no oficiales de WhatsApp Web: arriesgan el bloqueo del número). Interfaz lista para otro proveedor.
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
  (Postgres solo usa la clave al inicializar).
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
- HECHO (Fase 2, 2026-10-29): migración 0005 (sesiones, asistencias, justificaciones, multas). **115 pruebas**.
  - Sesiones por rama (`POST /sesiones` o `/sesiones/programar` por días de la semana, máx. ~6 meses; no en el
    pasado). Esperados = alumnos activos de la rama con inscripción vigente desde antes de la sesión.
  - Marcación: grupo (`asistencia.marcar_grupo`, Entrenador solo su rama; presente/ausente; no sesiones futuras)
    o propia (Miembro, solo el día y entre `minutos_marcar_antes` antes del inicio y el fin; no pisa lo del staff).
  - Cierre (`POST /sesiones/cerrar`, `asistencia.corregir`; lo llamará el worker): tras `hora_cierre_asistencia`,
    quien no marcó ni justificó → ausente + multa (`multa_inasistencia`, copiada; 0 = no multar). Justificación
    pendiente deja la decisión a la revisión. `with_for_update(skip_locked)` evita cierres duplicados.
  - Justificación: Miembro hasta `dias_para_justificar` tras la sesión; staff sin plazo. Revisión
    (`justificaciones.revisar`, Admin/SA): aprobar → justificado y anula multa pendiente; rechazar tras el cierre →
    ausente + multa. El motivo (posibles datos de salud) NO va a la auditoría.
  - Corrección tras el cierre (`asistencia.corregir`, con motivo) ajusta la multa. Cancelar sesión anula sus multas
    pendientes. Multas: pago con `pagos.registrar` (Admin/SA; el Entrenador no cobra), anular pendiente con
    `multas.anular` + motivo; una pagada no se anula (devolución manual, fuera de alcance).
  - Alertas `GET /sesiones/alertas`: racha de ausencias (justificada rompe la racha) ≥ `inasistencias_consecutivas_aviso`.
  - Reloj: todo el código usa `fechas.ahora()`/`fechas.hoy()` (las pruebas lo simulan con monkeypatch).
- HECHO (worker, 2026-10-29): servicio `worker` en docker-compose (`python -m app.worker`, `app/worker.py`). Corre
  tareas idempotentes por intervalo: cierre de asistencia cada 300 s y vencimiento de inscripciones cada 3600 s
  (`WORKER_*_SEGUNDOS`). `pg_try_advisory_xact_lock` evita dos workers en la misma tarea; un fallo no lo tumba;
  latido en /tmp/worker_latido para el healthcheck. No recarga solo: `docker compose restart worker` tras cambios.
  Toda tarea nueva debe ser idempotente y registrarse en `worker.tareas()`. **119 pruebas**.
- HECHO (Fase 3A rifas, 2026-10-29): migración 0006 (rifas, talonarios, puestos, pagos_puesto, actas_sorteo). **133 pruebas**.
  - Crear rifa (`rifas.gestionar`): máx. `rifas_por_anio` no canceladas; copia `puestos_por_talonario` y
    `precio_puesto`; asigna talonario a cada alumno con inscripción vigente del año (puestos indice*N … +N-1).
    `POST /rifas/{id}/talonarios` asigna a los inscritos después.
  - Pagos por puesto o por talonario completo (se reparte en orden) con `pagos.registrar`; `pagos_puesto` append-only,
    anulación con motivo (`pagos.anular`, SA). Comprador (nombre/teléfono) con `rifas.gestionar`.
  - Sorteo (`sorteo.jugar`, desde `fecha_sorteo`): solo puestos de talonarios pagados al 100 %, `secrets.choice`,
    fila bloqueada (`refresh(with_for_update)`) antes de revisar el estado. Acta append-only con la lista de
    participantes y su SHA-256 (`services/rifas.huella`).
  - `GET /alumnos/{id}/estado-cuenta`: saldo de inscripción + multas pendientes + talonarios con saldo → `al_dia`
    (paz y salvo).
- HECHO (Fase 3B torneos, 2026-10-29): migración 0007 (torneos, equipos_torneo, pagos_equipo). **148 pruebas**.
  - Todo con `eventos.gestionar` (Admin/SA): guarda contactos de delegados externos. Pagos con `pagos.registrar`,
    anulación con `pagos.anular` (SA); `pagos_equipo` append-only. Se quitó el permiso `eventos.inscribir`.
  - Inscripción hasta `fecha_limite_inscripcion`; club único por torneo (sin importar mayúsculas, salvo retirado).
    Cupo lleno → `en_espera`; al retirarse uno que ocupaba cupo entra el primero en espera. Torneo bloqueado
    (`refresh(with_for_update)`) al mover el cupo. Abonos → `confirmado` al completar; valor 0 → confirmado directo.
  - Inscripción pública de clubes: queda para la fase del sitio público.
- HECHO (notificaciones, 2026-10-29): migración 0008 (`notificaciones`). **160 pruebas**.
  - `services/notificaciones.avisar`: una fila por destinatario con bandeja/correo/WhatsApp; `clave` única +
    `ON CONFLICT DO NOTHING ... RETURNING` = idempotente. Sin canal posible → no se crea.
  - Destinatarios: acudientes + el alumno si es mayor (correo propio o el de su cuenta). Staff = SA/Admin +
    entrenadores de la rama (solo bandeja/correo).
  - Por evento: multa generada, justificación revisada, inscripción vencida. Programados (worker, cada hora):
    recordatorios de pago (`recordatorios_dias_antes`, el umbral más cercano, clave con fecha límite) y alertas de
    inasistencia (una por racha). WhatsApp solo para recordatorio/vencida/multa.
  - Correo: `core/correo.py` (SMTP o modo registro, `EMAIL_MODO`); el worker envía cada 60 s en lotes de 50,
    reintentos con espera 2^n min, 5 intentos → fallido. `POST /notificaciones/correo-prueba` (SA) para probar Gmail.
  - Rutas: `/notificaciones/mias` (cualquiera, solo las propias), `/whatsapp` y `/correos` (`notificaciones.gestionar`).
- HECHO (mora, 2026-10-29): migración 0009 (`inscripciones.causa_expulsion` mora|manual). **168 pruebas**.
  - `services/mora.py`: multa vence en la fecha de la sesión; talonario, en la fecha del sorteo. Mora cuando la
    deuda vencida más antigua + `meses_mora_expulsion` (con `fechas.sumar_meses`) ≤ hoy.
  - Worker (tarea `mora`, cada hora): activo→a_expulsar (o expulsado) con causa "mora"; a_expulsar por mora → activo
    al pagar; lo marcado a mano nunca lo revierte. Aviso a la familia `dias_aviso_mora` antes, al entrar en mora y al
    salir; aviso al staff cuando hay expulsión por confirmar. Usa la inscripción activa más reciente (cruza años).
  - `GET /mora` (staff; Entrenador su rama) y `en_mora`/`entra_en_mora` en el estado de cuenta.
- HECHO (frontend F1, 2026-10-29): servicio `frontend` (node:22, `http://localhost:4300`; el 4200 lo usa otro
  proyecto en este PC), proxy `/api`→api. Login, marco (lateral/superior/pestañas móviles + "Más"), menú filtrado
  por permisos desde `core/secciones.ts` (también genera las rutas), bandeja de avisos real, demás secciones
  "en construcción". 9 pruebas de frontend (token en memoria, renovación única ante 401, sin token a otros
  dominios, logout, menú por permisos, sin redirección abierta). CI: npm audit + build + tests.
- HECHO (Resumen, 2026-10-29): `GET /api/v1/resumen` (staff; Entrenador su rama; `services/resumen.py`):
  indicadores, alertas ordenadas por gravedad con `ruta` del frontend, sesiones de hoy, rifas del año, cartera y
  próximo torneo (solo con `eventos.gestionar`). Pantalla Resumen: tablero del staff como el prototipo; las
  familias ven a sus hijos (estado de cuenta) y próximos entrenamientos. 173 pruebas backend, 14 frontend.
  Pipe `pesos` en `compartido/`.
  Mensajes de resultado con `compartido/aviso.ts` (`<app-aviso>`): X para cerrar; los de éxito se cierran solos
  a los 6 s, los errores se quedan hasta cerrarlos. Usarlo en todas las pantallas nuevas. Pantallas construidas se registran en `PANTALLAS` de `app.routes.ts`.
- HECHO (Asistencia, 2026-10-29): pantalla `paginas/asistencia/`. Semana navegable (+ filtro de rama con
  `alumnos.ver_todos`), tira de sesiones, planilla P/A con "Todos presentes" (solo abierta y no futura), "Corregir"
  con motivo tras el cierre, cancelar y programar sesiones (una fecha → `POST /sesiones`; rango + días →
  `/programar`), justificaciones por revisar (rechazo exige comentario) y racha de inasistencias. La familia ve
  solo sus filas: "Marcar presente" (hoy) y "Justificar", e historial de sus justificaciones. Compartidos nuevos:
  `compartido/fechas.ts`, `compartido/errores.ts` (`mensajeError`: detalle de la API, nunca trazas) y estilos
  globales `.control`, `.mensaje`, `.boton.chico`.
- HECHO (entrenamiento general, 2026-10-29): migración 0010 (sesiones sin `rama`, `automatica`,
  `causa_cancelacion` festivo|torneo|horario|manual, única por fecha+hora; tabla `horario_entrenamiento`, sembrada
  L/X 18–20 y S 16–18). `core/festivos.py` (Ley Emiliani + Pascua). `services/programacion.py`: `generar` crea
  desde **mañana** hasta `dias_programacion_anticipada` (60) días; festivo → creada cancelada; torneo programado →
  cancela y, si el torneo se cancela, reactiva (lo llaman torneos.crear/cancelar y el worker cada hora, tarea
  `programar_sesiones`); solo toca las automáticas. `PUT /sesiones/horario` (`sesiones.gestionar`, ya NO lo tiene
  el Entrenador): ajusta/borra/cancela (si tiene registros) las futuras y regenera. `POST /sesiones` = sesión extra.
  Esperados = ambas ramas; la planilla se limita con `filtro_visibles` (Entrenador marca solo su rama).
  Frontend: formularios en **popups** (`compartido/dialogo.ts`, `<dialog>` modal; el error de la API se muestra
  dentro del popup) — las marcas P/A siguen en la lista por rapidez.
  `POST /sesiones/{id}/reactivar` (`sesiones.gestionar`): deshace una cancelación manual o por festivo, solo antes
  del cierre de esa sesión (si no, el cierre multaría a todos); las de torneo/horario no (las maneja la
  programación). Botón "Deshacer cancelación" / "Entrenar este festivo". Avisos: **campana desplegable**
  (`layout/campana/`), ya no hay página `/notificaciones`. 181 pruebas backend, 28 frontend.
- HECHO (Alumnos, 2026-10-30): pantalla `paginas/alumnos/` como el prototipo: lista (búsqueda con espera de 300 ms,
  filtros de rama solo con `alumnos.ver_todos`, "Inactivos"; punto de color por inscripción) y ficha (`?id=` en la
  URL): datos, acudientes, estado de cuenta, historial de asistencia con multas y documentos (subir/descargar con
  token/eliminar). Popups: nuevo/editar alumno, agregar acudiente (se busca por documento completo y se reutiliza;
  si no existe se crea, y un reintento no lo duplica), quitar acudiente, subir/eliminar documento. "Ver completo"
  del documento solo Admin/SA (auditado). La familia ve solo lo suyo, sin botones de edición. En celular: lista o ficha.
  Backend: `GET /alumnos` acepta `activo` y busca también por documento **completo** (índice ciego en cada tipo;
  nunca parcial) y trae `inscripcion_estado` del año; `GET /alumnos/{id}/asistencia` (historial + multa, mismo
  alcance que la ficha). Compartidos: `compartido/estados.ts`, `.boton.peligro` global. 184 pruebas backend, 34 frontend.
- HECHO (revisión de calidad, 2026-10-30): **ESLint** (`frontend/eslint.config.js`: typescript-eslint strict +
  angular-eslint con accesibilidad de plantillas; `npm run lint`) y **ruff** (`backend/ruff.toml`: E/W/F/I/B/UP/S/
  SIM/C4/DTZ/RUF, línea 120; las migraciones no se reordenan) en limpio y en el CI. Fixtures compartidas (`reloj`,
  `h_admin`, `h_root`, `familia`) en `tests/conftest.py` y acciones (`crear_sesion`, `alumno_inscrito`, `crear_rifa`…)
  en `tests/fabrica.py`: **nunca importar de otro `test_*.py`**. `raise ... from` en los except.
  Editor: `node_modules` del PC (`npm ci` en `frontend/`) y `backend/.venv` solo para que VS Code resuelva tipos;
  Docker usa los suyos. Resumen: `alumnos_sin_inscripcion` ("registrados sin inscribir"). Alumnos: inscribir al
  crear o desde la ficha ("Inscribir <año>") con sin pago / abono parcial / pago completo (`inscripciones.crear` y
  `.abonar`); si la inscripción falla tras crear, se avisa sin reintentar el alta. 184 pruebas backend, 37 frontend.
- HECHO (Inscripciones, 2026-10-30): pantalla `paginas/inscripciones/`: año navegable, filtro de rama (ver_todos),
  indicadores (activas, por cobrar, vencen en 7 días, en revisión), filtros por estado con conteo (por defecto
  pendientes, la más urgente primero), fila con fechas, días restantes, barra de pagado y acciones rápidas (abono con
  el saldo prellenado, prórroga). Detalle en popup: cifras, abonos (anular con motivo: `pagos.anular`), prórrogas y
  cambios de estado según `TRANSICIONES` (confirmar expulsión solo con `expulsion.confirmar`). "Nueva inscripción"
  busca alumnos (deshabilita a quien ya tiene una vigente). `inscripciones/inscribir.ts` (`inscribirConPago`,
  `problemaPago`, `resumenPago`) lo comparten Alumnos e Inscripciones. KPIs (`.kpis/.kpi`) ahora son estilos
  globales. La familia ve las de sus hijos sin acciones. 184 pruebas backend, 44 frontend.
- HECHO (Alumnos + Inscripciones unificados, 2026-10-30): alumno (persona, dura años) e inscripción (matrícula
  anual con pago) siguen separados en datos, pero la experiencia es una: `POST /inscripciones/alumno-nuevo`
  (`inscripciones.crear` + `alumnos.editar`, y `.abonar` si trae pago) crea ficha + inscripción de hoy + primer
  pago (`ninguno|parcial|completo`) en **una transacción** (si algo falla no queda nada). Menú: solo "Alumnos",
  con pestañas `PestanasAlumnos` (Fichas `/alumnos` · Inscripciones y pagos `/alumnos/inscripciones`;
  `/inscripciones` redirige; `Seccion.enMenu: false`). "Inscribir alumno nuevo" (inscripción obligatoria); la ficha
  muestra la tarjeta "Inscripción <año>" (pagado, saldo, límite, "Registrar abono", enlace `?id=` al detalle) y
  "Renovar inscripción" si no tiene vigente; en la pestaña de inscripciones "Renovar alumno existente". Pestañas
  móviles: Resumen, Asistencia, Alumnos, Multas. Estilos de formularios de popups (`.formulario`, `.rejilla`,
  `.campo`, `.casilla`, `.acciones`…) ahora globales. La explicación de la regla va en un modal (botón "?" junto al título). 189 pruebas backend, 46 frontend.
- HECHO (ayuda + Multas y mora, 2026-10-30): botón "?" en el encabezado de **todas** las vistas
  (`compartido/ayuda.ts`; el texto de cada una en `core/ayudas.ts`, por ruta; cada paso puede limitarse por
  permisos). Pantalla `paginas/multas/`: por cobrar agrupadas por alumno (quien más debe primero, "Cobrar todo" o
  una), pagadas y anuladas (historial), anular con motivo (`multas.anular`), panel "Riesgo de mora" (`GET /mora`,
  en mora primero, "entra en mora en N d") e indicadores. Backend: `POST /multas/pagos` cobra varias en una
  transacción (todas o ninguna, filas bloqueadas en orden), `MultaOut.rama`, y `obtener_visible` bloquea la multa
  (`with_for_update`). Estilos globales nuevos: `.filtros/.filtro`, `.enlace-rojo`. 190 pruebas backend, 53 frontend.
- HECHO (Rifas, 2026-10-30): pantalla `paginas/rifas/`: año navegable, indicadores, tarjetas por rifa (premio,
  paz y salvo, recaudo, sorteo "en N d"; acciones: jugar sorteo desde la fecha con `sorteo.jugar`, ver acta, asignar
  talonarios a nuevos inscritos, cancelar con motivo) y matriz "Paz y salvo por alumno" (alumno × rifa, ✓ o saldo,
  deuda total, filtros con deuda/rama). Talonario en popup: 20 puestos, "Registrar pago" (se reparte en orden);
  popup por puesto: comprador (`rifas.gestionar`), pago (`pagos.registrar`), historial y anular (`pagos.anular`).
  Sorteo: puestos en la urna y acta (ganador, comprador, participantes, huella SHA-256). Sin cambios en backend.
  190 pruebas backend, 60 frontend.
- HECHO (código del alumno + vista Sorteo, 2026-10-30): migración 0011 (`alumnos.codigo` único con check
  `^[FM][0-9]{3,5}$`, relleno por rama en orden de creación; `talonarios.codigo`). `alumnos.siguiente_codigo`
  con `pg_advisory_xact_lock(7311)` (sin choques entre altas simultáneas). Búsqueda por código. API: `codigo` en
  AlumnoOut/TalonarioOut, `boleta` (1…20) en PuestoOut, `codigo`/`boleta`/`rama` en ActaOut. Frontend: pestañas
  genéricas `compartido/pestanas.ts` (Alumnos y Rifas), pestaña **Sorteo** (`/rifas/sorteo`, `?rifa=`): KPIs,
  pantalla grande código · boleta que gira (solo visual: el ganador lo elige el servidor; respeta
  `prefers-reduced-motion`), confirmación antes de jugar, tarjeta del ganador con acta y "Avisar por WhatsApp"
  (wa.me al teléfono del comprador, `numeroWhatsApp`), talonarios por código con filtros, avance por rama e
  historial de sorteos del año. 192 pruebas backend, 65 frontend.
- SIGUIENTE (frontend): Torneos, Avisos, Configuración,
  Usuarios. Las alertas se notificarán en la fase de notificaciones (Redis
  llegará ahí para colas y para el limitador de logins).
- Después: frontend Angular, club público, IA, producción.

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
- Repositorio git local (rama `main`, desde 2026-10-29). Un commit al cerrar cada fase o cambio relevante;
  antes de cada commit verificar que no se cuelen secretos (`.env`, claves).
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
docker compose run --rm --user root api sh -c "pip install -q -r requirements-dev.txt && pytest"
docker compose exec frontend npx ng test --watch=false      # pruebas del frontend
cd frontend; npm run lint                                    # ESLint (requiere npm ci en el PC)
docker compose run --rm --user root api sh -c "pip install -q ruff && ruff check ."
```
Si el puerto 8000 está ocupado: `API_PORT=8001` en `.env`.

## Documentación de diseño
Documento completo "Dragones – Documento de diseño y desarrollo" (modelo de datos, roles, reglas, API, seguridad, IA, fases).
