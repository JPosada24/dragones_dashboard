"""Catálogo de permisos y roles. Es la fuente de verdad que se siembra en la base de datos."""

PERMISOS: dict[str, str] = {
    "usuarios.gestionar": "Crear usuarios, cambiar roles y desactivar cuentas",
    "config.ver": "Ver los parámetros del club",
    "config.editar": "Cambiar parámetros críticos (multa, plazos, políticas)",
    "auditoria.ver": "Consultar la bitácora de auditoría",
    "alumnos.ver_todos": "Ver fichas de todos los alumnos",
    "alumnos.ver_documento": "Ver el número de documento completo (cada consulta queda en la auditoría)",
    "alumnos.ver_propios": "Ver sus propios datos o los de sus hijos",
    "alumnos.editar": "Crear y editar alumnos, acudientes y documentos",
    "alumnos.eliminar": "Eliminar un alumno con toda su información (no se puede deshacer)",
    "inscripciones.crear": "Inscribir alumnos",
    "inscripciones.gestionar": "Gestionar inscripciones (estados, vencimientos, fechas anteriores)",
    "inscripciones.abonar": "Registrar abonos de inscripción",
    "prorroga.conceder": "Conceder prórrogas de pago",
    "expulsion.confirmar": "Confirmar una expulsión",
    "sesiones.gestionar": "Cambiar el horario de entrenamiento, crear, cancelar y eliminar sesiones extra",
    "asistencia.marcar_propia": "Marcar asistencia o justificar la propia (o la de sus hijos)",
    "asistencia.marcar_grupo": "Marcar la asistencia de la planilla",
    "asistencia.corregir": "Corregir asistencia ya cerrada",
    "justificaciones.revisar": "Aprobar o rechazar justificaciones",
    "pagos.registrar": "Registrar pagos de multas, rifas y paz y salvo",
    "pagos.anular": "Anular un abono o pago registrado por error",
    "multas.anular": "Anular una multa pendiente",
    "rifas.gestionar": "Crear y gestionar rifas y talonarios",
    "sorteo.jugar": "Jugar el sorteo de una rifa",
    "eventos.gestionar": "Crear torneos e inscribir los clubes participantes",
    "notificaciones.gestionar": "Ver y enviar los avisos por WhatsApp y revisar el estado de los correos",
    "club.editar": "Editar el perfil público del club",
    "agente.usar": "Usar el asistente de IA",
    "anio.cerrar": "Cerrar el año deportivo",
    "respaldo.exportar": "Exportar respaldos",
}

ROLES: dict[str, tuple[str, str]] = {
    "SUPERADMIN": ("SuperAdmin", "Dueño y entrenador principal del club: acceso total y parámetros críticos"),
    "ADMIN": ("Admin", "Coordinación y pagos del día a día"),
    "ENTRENADOR": ("Entrenador", "Entrenador asistente: alumnos de ambas ramas, asistencia e inscripciones; no cobra"),
    "MIEMBRO": ("Miembro", "Alumno mayor de edad o acudiente"),
}

ROLES_PERMISOS: dict[str, set[str]] = {
    "SUPERADMIN": set(PERMISOS),
    "ADMIN": {
        "config.ver", "auditoria.ver",
        "alumnos.ver_todos", "alumnos.ver_documento", "alumnos.editar",
        "inscripciones.crear", "inscripciones.gestionar", "inscripciones.abonar", "prorroga.conceder",
        "sesiones.gestionar", "asistencia.marcar_grupo", "asistencia.corregir", "justificaciones.revisar",
        "pagos.registrar", "multas.anular", "rifas.gestionar", "sorteo.jugar",
        "eventos.gestionar", "notificaciones.gestionar", "club.editar", "agente.usar",
    },
    # El Entrenador es general (ambas ramas) y hace todo el proceso de inscripción (alumno, acudiente, documentos,
    # inscripción). No cobra multas ni rifas, no ve el documento completo ni gestiona horarios ni prórrogas.
    "ENTRENADOR": {
        "alumnos.ver_todos", "alumnos.editar", "inscripciones.crear", "inscripciones.abonar",
        "asistencia.marcar_grupo", "agente.usar",
    },
    "MIEMBRO": {
        # Solo consulta: ningún alumno ni acudiente se inscribe por su cuenta.
        "alumnos.ver_propios",
        "asistencia.marcar_propia", "agente.usar",
    },
}
