"""Catálogo de permisos y roles. Es la fuente de verdad que se siembra en la base de datos."""

PERMISOS: dict[str, str] = {
    "usuarios.gestionar": "Crear usuarios, cambiar roles y desactivar cuentas",
    "config.ver": "Ver los parámetros del club",
    "config.editar": "Cambiar parámetros críticos (multa, plazos, políticas)",
    "auditoria.ver": "Consultar la bitácora de auditoría",
    "alumnos.ver_todos": "Ver fichas de todos los alumnos",
    "alumnos.ver_rama": "Ver fichas de los alumnos de su rama",
    "alumnos.ver_propios": "Ver sus propios datos o los de sus hijos",
    "alumnos.editar": "Crear y editar alumnos, acudientes y documentos (el Entrenador, solo de su rama)",
    "inscripciones.crear": "Inscribir alumnos (el Entrenador, solo de su rama)",
    "inscripciones.gestionar": "Gestionar inscripciones (estados, vencimientos, fechas anteriores)",
    "inscripciones.abonar": "Registrar abonos de inscripción (el Entrenador, solo de su rama)",
    "prorroga.conceder": "Conceder prórrogas de pago",
    "expulsion.confirmar": "Confirmar una expulsión",
    "asistencia.marcar_propia": "Marcar asistencia o justificar la propia",
    "asistencia.marcar_grupo": "Marcar asistencia de un grupo",
    "asistencia.corregir": "Corregir asistencia ya cerrada",
    "justificaciones.revisar": "Aprobar o rechazar justificaciones",
    "pagos.registrar": "Registrar pagos de multas, rifas y paz y salvo",
    "pagos.anular": "Anular un abono o pago registrado por error (con motivo)",
    "rifas.gestionar": "Crear y gestionar rifas y talonarios",
    "sorteo.jugar": "Jugar el sorteo de una rifa",
    "eventos.gestionar": "Crear y editar eventos",
    "eventos.inscribir": "Inscribirse a eventos",
    "club.editar": "Editar el perfil público del club",
    "agente.usar": "Usar el asistente de IA",
    "anio.cerrar": "Cerrar el año deportivo",
    "respaldo.exportar": "Exportar respaldos",
}

ROLES: dict[str, tuple[str, str]] = {
    "SUPERADMIN": ("SuperAdmin", "Dueño y entrenador principal del club: acceso total y parámetros críticos"),
    "ADMIN": ("Admin", "Coordinación y pagos del día a día"),
    "ENTRENADOR": ("Entrenador", "Entrenador asistente: gestiona solo los alumnos de su rama"),
    "MIEMBRO": ("Miembro", "Alumno mayor de edad o acudiente"),
}

ROLES_PERMISOS: dict[str, set[str]] = {
    "SUPERADMIN": set(PERMISOS),
    "ADMIN": {
        "config.ver", "auditoria.ver",
        "alumnos.ver_todos", "alumnos.editar",
        "inscripciones.crear", "inscripciones.gestionar", "inscripciones.abonar", "prorroga.conceder",
        "asistencia.marcar_grupo", "asistencia.corregir", "justificaciones.revisar",
        "pagos.registrar", "rifas.gestionar", "sorteo.jugar",
        "eventos.gestionar", "eventos.inscribir", "club.editar", "agente.usar",
    },
    # El Entrenador hace todo el proceso de inscripción de su rama (alumno, acudiente, documentos, inscripción).
    "ENTRENADOR": {
        "alumnos.ver_rama", "alumnos.editar", "inscripciones.crear", "inscripciones.abonar",
        "asistencia.marcar_grupo", "agente.usar",
    },
    "MIEMBRO": {
        # Solo consulta: ningún alumno ni acudiente se inscribe por su cuenta.
        "alumnos.ver_propios",
        "asistencia.marcar_propia", "eventos.inscribir", "agente.usar",
    },
}
