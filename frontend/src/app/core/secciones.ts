/** Mapa de la aplicación: de aquí salen el menú lateral, las pestañas del celular y las rutas. */

const VER_ALUMNOS = ['alumnos.ver_todos', 'alumnos.ver_rama', 'alumnos.ver_propios'];

export interface Seccion {
  ruta: string; // sin "/" inicial ('' = inicio)
  etiqueta: string;
  icono: string; // nombre de Material Symbols
  grupo: 'Día a día' | 'Dinero' | 'Club' | 'Sistema';
  permisos: string[]; // basta con uno; vacío = cualquiera con sesión
  titulo: string;
  subtitulo: string;
  descripcion: string; // qué tendrá la pantalla (se muestra mientras se construye)
  /** false = tiene ruta pero no entrada propia en el menú (es una pestaña de otra sección). */
  enMenu?: false;
}

export const SECCIONES: Seccion[] = [
  {
    ruta: '', etiqueta: 'Resumen', icono: 'space_dashboard', grupo: 'Día a día', permisos: [],
    titulo: 'Resumen del club', subtitulo: 'Lo importante de hoy',
    descripcion: 'Indicadores del club, alertas que requieren decisión, entrenamiento de hoy y cartera.',
  },
  {
    ruta: 'asistencia', etiqueta: 'Asistencia', icono: 'fact_check', grupo: 'Día a día', permisos: VER_ALUMNOS,
    titulo: 'Asistencia', subtitulo: 'Cierre automático a las 11:59 pm',
    descripcion: 'Sesiones por rama, planilla para marcar, justificaciones por revisar y alertas de inasistencia.',
  },
  {
    ruta: 'alumnos', etiqueta: 'Alumnos', icono: 'groups', grupo: 'Día a día', permisos: VER_ALUMNOS,
    titulo: 'Alumnos', subtitulo: 'Fichas, inscripciones y pagos',
    descripcion: 'Ficha del alumno con acudientes, documentos, estado de cuenta e historial.',
  },
  {
    // Pestaña de Alumnos: la ruta anida bajo /alumnos para que el menú marque "Alumnos".
    ruta: 'alumnos/inscripciones', etiqueta: 'Inscripciones', icono: 'assignment', grupo: 'Día a día',
    permisos: VER_ALUMNOS, enMenu: false,
    titulo: 'Alumnos', subtitulo: 'Inscripciones del año: plazos, abonos y prórrogas',
    descripcion: 'Inscripciones pendientes de pago, abonos, prórrogas y cambios de estado.',
  },
  {
    ruta: 'rifas', etiqueta: 'Rifas', icono: 'payments', grupo: 'Dinero', permisos: VER_ALUMNOS,
    titulo: 'Rifas', subtitulo: 'Talonarios, pagos y sorteo',
    descripcion: 'Rifas del año, talonarios por alumno, pagos de puestos, sorteo y acta.',
  },  {
    // Pestaña de Rifas (anidada bajo /rifas para que el menú marque "Rifas").
    ruta: 'rifas/sorteo', etiqueta: 'Sorteo', icono: 'casino', grupo: 'Dinero', permisos: VER_ALUMNOS, enMenu: false,
    titulo: 'Rifas', subtitulo: 'Sorteo: entran los talonarios pagados al 100 %',
    descripcion: 'Sorteo de la rifa con su acta.',
  },

  {
    ruta: 'multas', etiqueta: 'Multas y mora', icono: 'gavel', grupo: 'Dinero', permisos: VER_ALUMNOS,
    titulo: 'Multas y mora', subtitulo: 'Deudas por cobrar',
    descripcion: 'Multas por inasistencia, pagos y alumnos en riesgo o en mora.',
  },
  {
    ruta: 'torneos', etiqueta: 'Torneos', icono: 'emoji_events', grupo: 'Club', permisos: ['eventos.gestionar'],
    titulo: 'Torneos', subtitulo: 'Clubes inscritos, cupo y pagos',
    descripcion: 'Torneos del club con clubes inscritos, lista de espera y pagos.',
  },
  {
    ruta: 'avisos', etiqueta: 'Avisos WhatsApp', icono: 'chat', grupo: 'Club', permisos: ['notificaciones.gestionar'],
    titulo: 'Avisos por WhatsApp', subtitulo: 'Mensajes listos para enviar con un clic',
    descripcion: 'Cola de avisos con el enlace de WhatsApp listo, y estado de los correos enviados.',
  },
  {
    ruta: 'configuracion', etiqueta: 'Configuración', icono: 'settings', grupo: 'Sistema', permisos: ['config.ver'],
    titulo: 'Configuración', subtitulo: 'Parámetros del club',
    descripcion: 'Multa, plazos, valores, mora y demás parámetros (solo el SuperAdmin los cambia).',
  },
  {
    ruta: 'usuarios', etiqueta: 'Usuarios', icono: 'manage_accounts', grupo: 'Sistema', permisos: ['usuarios.gestionar'],
    titulo: 'Usuarios', subtitulo: 'Cuentas y roles',
    descripcion: 'Crear cuentas, asignar roles y ramas, y desactivar accesos.',
  },
];

export const GRUPOS = ['Día a día', 'Dinero', 'Club', 'Sistema'] as const;

/** Pestañas fijas en el celular (las demás van en "Más"). */
export const PESTANAS_MOVIL = ['', 'asistencia', 'alumnos', 'multas'];

export function seccionesVisibles(tienePermiso: (permisos: string[]) => boolean): Seccion[] {
  return SECCIONES.filter((s) => s.enMenu !== false && tienePermiso(s.permisos));
}
