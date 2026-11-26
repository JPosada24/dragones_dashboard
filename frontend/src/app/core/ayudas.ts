import { Ayuda } from '../compartido/ayuda';

/**
 * Explicación de cada vista: la cuenta Kiira la primera vez que se entra y la repite el botón «?». La clave es la ruta
 * de `secciones.ts`. Corta a propósito: lo que hace falta para usar la pantalla, sin detalles técnicos.
 */
export const AYUDAS: Record<string, Ayuda> = {
  '': {
    titulo: 'Cómo leer el resumen',
    pasos: [
      { titulo: 'Indicadores', texto: 'Alumnos con inscripción vigente, inscripciones por cobrar, multas sin pagar y alertas abiertas.' },
      { titulo: 'Alertas', texto: 'Lo que necesita una decisión, de lo más urgente a lo menos. «Revisar» te lleva a donde se resuelve.' },
      { titulo: 'Entrenamiento de hoy', texto: 'Cuántos marcaron o faltan. A las 11:59 pm el sistema cierra el día.' },
      { titulo: 'Cartera', texto: 'Lo que le deben al club: inscripciones, multas y talonarios de rifa.' },
    ],
  },
  asistencia: {
    titulo: 'Cómo funciona la asistencia',
    pasos: [
      { titulo: 'Programación automática', texto: 'Los entrenamientos salen solos del horario semanal. Los festivos y los torneos del club los cancelan; para reponer se crea una sesión extra.' },
      { titulo: 'Marcar', texto: 'El entrenador marca presente o ausente en la planilla.' },
      { titulo: 'Cierre del día', texto: 'A las 11:59 pm, quien no quedó marcado como presente ni justificado queda ausente y con multa (por defecto $2.000).' },
      { titulo: 'Cancelar', texto: 'Cancelar una sesión anula sus multas pendientes. Se puede deshacer hasta el cierre de ese día; las sesiones extra también se pueden eliminar.', permisos: ['sesiones.gestionar'] },
    ],
  },
  alumnos: {
    titulo: 'Cómo funcionan las fichas',
    intro: 'Cada alumno tiene una ficha que dura años; la inscripción se renueva cada año.',
    pasos: [
      { titulo: 'Inscribir alumno nuevo', texto: 'En un solo paso: sus datos, el acudiente, la inscripción del año y el primer pago.', permisos: ['inscripciones.crear'] },
      { titulo: 'Acudientes', texto: 'Los menores de edad necesitan al menos uno. Si ya está registrado (por ejemplo, de un hermano), se reutiliza.' },
      { titulo: 'Inscripción del año', texto: 'La ficha muestra lo pagado, el saldo y el límite. Quien viene del año pasado se renueva con «Renovar inscripción».' },
      { titulo: 'Autorización de datos', texto: 'Cada alumno necesita la autorización de su acudiente (o la suya si es mayor de edad). Si falta, la ficha lo marca en rojo con «Registrar».', permisos: ['alumnos.editar'] },
      { titulo: 'Inactivo o eliminar', texto: 'Si deja el club, se desactiva desde «Editar» y su historial se conserva. Eliminarlo borra toda su información y no se puede deshacer.', permisos: ['alumnos.editar'] },
    ],
  },
  'alumnos/inscripciones': {
    titulo: 'Cómo funcionan las inscripciones',
    pasos: [
      { titulo: 'Valor y plazo', texto: 'Por defecto $90.000 y 30 días para pagar; se cambian en Configuración.' },
      { titulo: 'Abonos', texto: 'Se aceptan pagos parciales. Al completar el valor, la inscripción queda activa.' },
      { titulo: 'Vencimiento y prórroga', texto: 'Si el plazo termina sin completar el pago, la inscripción se rechaza. Admin o SuperAdmin pueden dar una prórroga.' },
    ],
    nota: 'Un abono errado no se borra: se anula y queda en el historial.',
  },
  rifas: {
    titulo: 'Cómo funcionan las rifas',
    pasos: [
      { titulo: 'Talonario', texto: 'Cada rifa le da a cada alumno inscrito un talonario de 20 boletas de $2.000 ($40.000). Las boletas se leen con su código: F012-01 a F012-20.' },
      { titulo: 'Pagos', texto: 'El talonario se paga completo o por abonos. Pagado al 100 % queda a paz y salvo; si queda saldo después del sorteo, cuenta como deuda.' },
      { titulo: 'Sorteo', texto: 'En la pestaña Sorteo, desde su fecha. Solo participan los talonarios pagados al 100 %.' },
    ],
  },
  'rifas/sorteo': {
    titulo: 'Cómo funciona el sorteo',
    pasos: [
      { titulo: 'La urna', texto: 'Solo entran las boletas de los talonarios pagados al 100 %.' },
      { titulo: 'Jugar', texto: '«Jugar la rifa» elige una boleta al azar, por ejemplo F012-07 (la boleta 7 del talonario de F012). Se puede jugar varias veces para varios premios; una boleta que ya ganó no vuelve a la urna.', permisos: ['sorteo.jugar'] },
      { titulo: 'Acta', texto: 'Cada jugada deja un acta con la boleta ganadora y su dueño. No se puede modificar.' },
      { titulo: 'Aviso', texto: '«Avisar por WhatsApp» abre el mensaje listo para enviarlo desde el número del club.' },
    ],
  },
  habeas: {
    titulo: 'Solicitudes de datos personales',
    intro: 'Si alguien pide conocer, corregir o borrar sus datos, regístralo aquí: la ley fija el plazo para responder.',
    pasos: [
      { titulo: 'Consulta', texto: 'Conocer qué datos tiene el club. Plazo: 10 días hábiles.' },
      { titulo: 'Reclamo', texto: 'Corregir, borrar o retirar la autorización. Plazo: 15 días hábiles.' },
      { titulo: 'Avisos', texto: 'El Resumen avisa cuando a una solicitud le quedan 3 días hábiles o menos.' },
    ],
  },
  reportes: {
    titulo: 'Cómo leer los reportes',
    intro: 'Todo el dinero que entró al club: inscripciones, multas, rifas y torneos.',
    pasos: [
      { titulo: 'Por mes', texto: 'Cada pago cuenta en su fecha; una anulación resta en el mes en que se hizo.' },
      { titulo: 'Exportar', texto: 'Descarga los movimientos del rango en un archivo que abre Excel.', permisos: ['reportes.exportar'] },
    ],
  },
  multas: {
    titulo: 'Cómo funcionan las multas y la mora',
    pasos: [
      { titulo: 'Multa', texto: 'Se genera al cierre del día a quien faltó sin justificar. Por defecto $2.000.' },
      { titulo: 'Pagar o anular', texto: 'Una multa pendiente se paga o se anula; una pagada ya no se anula.' },
      { titulo: 'Mora', texto: 'Cualquier deuda (multas o talonarios) con más de 3 meses sin pagar pone la inscripción en revisión. Si paga, vuelve a quedar activa.' },
    ],
  },
  torneos: {
    titulo: 'Cómo funcionan los torneos',
    pasos: [
      { titulo: 'Cupo', texto: 'Cada torneo tiene un cupo de equipos. Si se llena, los nuevos quedan en lista de espera y entran solos cuando alguien se retira.' },
      { titulo: 'Pagos', texto: 'Cada equipo paga la inscripción del torneo; se aceptan abonos y queda confirmado al completar.' },
      { titulo: 'Inscripción', texto: 'Desde el sitio, los clubes se inscriben hasta la fecha límite (o el día de inicio si no hay). Desde aquí puedes inscribir hasta el último día del torneo.' },
      { titulo: 'Grupos', texto: 'Con «Grupos» sorteas cada rama: entran todos los equipos con cupo, hayan pagado o no, y las cabezas de serie (estrella) quedan una por grupo. Al confirmar se publican en el sitio; quien llegue después va al grupo con menos equipos.' },
      { titulo: 'Anuncio', texto: 'Adjunta el flyer: el sitio lo muestra hasta que termine el torneo.' },
      { titulo: 'Al terminar', texto: '«Pasar a realizados» lo lleva a Perfil del club → Torneos realizados para agregarle los resultados.' },
    ],
    nota: 'Los días de torneo se cancelan los entrenamientos; si el torneo se cancela, vuelven.',
  },
  'perfil-club': {
    titulo: 'Cómo funciona el perfil del club',
    pasos: [
      { titulo: 'Sitio público', texto: 'Lo que escribas aquí (misión, historia, contacto, redes) es lo que muestra el sitio del club. Nada privado de los alumnos sale allí.' },
      { titulo: 'Publicar', texto: 'El interruptor general y el de cada álbum, video y entrenador deciden qué se ve.' },
      { titulo: 'Inscripciones de clubes', texto: 'Los clubes se inscriben a los torneos abiertos desde el sitio; te llega un aviso y aparecen en Torneos.' },
    ],
  },
  'perfil-club/galeria': {
    titulo: 'Cómo funciona la galería',
    pasos: [
      { titulo: 'Álbumes', texto: 'Cada álbum es una carpeta (un torneo, un entrenamiento…) con sus fotos. Uno en borrador no se ve en el sitio.' },
      { titulo: 'Videos', texto: 'Pega el enlace del video de TikTok, Instagram o YouTube.' },
    ],
    nota: 'Sube solo fotos con autorización de los acudientes de los menores que aparecen.',
  },
  'perfil-club/equipo': {
    titulo: 'Cómo funciona el equipo técnico',
    pasos: [
      { titulo: 'En el sitio', texto: 'Cada entrenador aparece con su foto, cargo y presentación. El orden más bajo va primero.' },
      { titulo: 'No es una cuenta', texto: 'Estos perfiles son solo para el sitio. Para que alguien entre a la plataforma, créale una cuenta en Usuarios.' },
    ],
  },
  'perfil-club/torneos': {
    titulo: 'Cómo funcionan los torneos realizados',
    pasos: [
      { titulo: 'En el sitio', texto: 'Cada torneo aparece con su afiche, fecha, lugar y reseña. Los más recientes van primero.' },
      { titulo: 'Fotos', texto: 'Puedes enlazar un álbum de la Galería: el sitio muestra «Ver fotos».' },
    ],
  },
  avisos: {
    titulo: 'Cómo funcionan los avisos',
    pasos: [
      { titulo: 'WhatsApp', texto: 'Cada aviso trae el mensaje listo: tócalo y se abre WhatsApp para enviarlo desde el número del club.' },
      { titulo: 'Cuándo se avisa', texto: 'Recordatorios de pago, inscripción vencida, multas y riesgo de mora.' },
    ],
  },
  configuracion: {
    titulo: 'Configuración del club',
    pasos: [
      { titulo: 'Parámetros', texto: 'Valor de la inscripción, plazo de pago, valor de la multa, meses para la mora y demás reglas.' },
      { titulo: 'Cambios', texto: 'Aplican a lo nuevo; lo ya creado conserva su valor.' },
    ],
  },
  usuarios: {
    titulo: 'Cuentas y roles',
    intro: 'La plataforma es del staff del club. Al crear una cuenta, la contraseña se muestra una sola vez para entregarla.',
    pasos: [
      { titulo: 'SuperAdmin', texto: 'Acceso total.' },
      { titulo: 'Admin', texto: 'Todo el club menos las cuentas de usuario.' },
      { titulo: 'Entrenador', texto: 'Alumnos, asistencia e inscripciones. No cobra multas ni rifas.' },
      { titulo: 'Permisos', texto: 'A un Admin o Entrenador puedes darle o quitarle permisos con el botón de ajustes de su cuenta.' },
      { titulo: 'Desactivar o eliminar', texto: 'Desactivar impide entrar sin borrar nada. Eliminar quita el acceso y conserva lo que registró.' },
    ],
  },
};
