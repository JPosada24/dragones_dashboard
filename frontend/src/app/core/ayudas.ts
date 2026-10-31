import { Ayuda } from '../compartido/ayuda';

/** Quien gestiona (todo el club o su rama); la familia no ve estos pasos. */
const STAFF = ['alumnos.ver_todos'];
const FAMILIA = ['alumnos.ver_propios'];

/** Explicación de cada vista (botón "?" junto al título). La clave es la ruta de `secciones.ts`. */
export const AYUDAS: Record<string, Ayuda> = {
  '': {
    titulo: 'Cómo leer el resumen',
    pasos: [
      { titulo: 'Indicadores', texto: 'Alumnos con inscripción vigente, inscripciones por cobrar, multas sin pagar y alertas abiertas.', permisos: STAFF },
      { titulo: 'Alertas', texto: 'Lo que necesita una decisión, de lo más grave a lo menos: expulsiones por confirmar, justificaciones, plazos por vencer, rachas de inasistencia y mora. "Revisar" te lleva a la pantalla donde se resuelve.', permisos: STAFF },
      { titulo: 'Entrenamiento de hoy', texto: 'Cuántos marcaron, justificaron o faltan. A las 11:59 pm el sistema cierra el día.', permisos: STAFF },
      { titulo: 'Cartera', texto: 'Lo que le deben al club: inscripciones, multas y talonarios de rifa.', permisos: STAFF },
      { titulo: 'Tus alumnos', texto: 'El estado de cuenta de cada uno. "A paz y salvo" significa que no debe nada.', permisos: FAMILIA },
      { titulo: 'Mora', texto: 'Si una deuda (multa o talonario) pasa de 3 meses sin pagar, la inscripción queda en revisión. Te avisamos antes de que ocurra.', permisos: FAMILIA },
    ],
  },
  asistencia: {
    titulo: 'Cómo funciona la asistencia',
    pasos: [
      { titulo: 'Programación automática', texto: 'Los entrenamientos salen solos del horario semanal (ambas ramas juntas). Los festivos de Colombia y los torneos del club los cancelan; para reponer se crea una sesión extra.' },
      { titulo: 'Marcar', texto: 'El entrenador marca presente o ausente en la planilla. La familia puede marcar "presente" el mismo día, dentro del horario.' },
      { titulo: 'Avisar que no asiste', texto: 'La familia avisa que el alumno no irá, sin tener que explicar el motivo. Si avisa antes de que empiece el entrenamiento queda justificado de una vez (sin multa); si avisa ya empezado o después, el staff aprueba o rechaza el aviso.' },
      { titulo: 'Cierre del día', texto: 'A las 11:59 pm, quien no marcó ni avisó queda ausente y con multa (por defecto $2.000). Si hay un aviso tardío por revisar, decide la revisión.' },
      { titulo: 'Cancelar y deshacer', texto: 'Una sesión se cancela (el motivo es opcional) y anula sus multas pendientes. Se puede deshacer hasta el cierre de ese día.', permisos: ['sesiones.gestionar'] },
      { titulo: 'Eliminar', texto: 'Las sesiones extra (creadas a mano) se pueden eliminar con la papelera; las del horario solo se cancelan. Si ya se cobraron multas de esa sesión, no se elimina.', permisos: ['sesiones.gestionar'] },
      { titulo: 'Rachas', texto: 'Tras varias ausencias seguidas aparece una alerta; una ausencia justificada corta la racha.', permisos: STAFF },
    ],
  },
  alumnos: {
    titulo: 'Cómo funcionan las fichas',
    intro: 'Cada alumno tiene una ficha que dura años; la inscripción se renueva cada año.',
    pasos: [
      { titulo: 'Inscribir alumno nuevo', texto: 'En un solo paso se registran sus datos, el acudiente, la inscripción del año y el primer pago. Si algo falla, no queda nada a medias.', permisos: ['inscripciones.crear'] },
      { titulo: 'Acudientes', texto: 'Los menores de edad necesitan al menos uno. Se busca por documento: si ya está registrado (por ejemplo, de un hermano), se reutiliza.' },
      { titulo: 'Inscripción del año', texto: 'La tarjeta de la ficha muestra lo pagado, el saldo y el límite. Quien viene del año pasado se renueva con "Renovar inscripción".' },
      { titulo: 'Documentos', texto: 'Solo PDF, JPG o PNG; se guardan cifrados. El número de documento completo solo lo ven Admin y SuperAdmin, y cada consulta queda registrada.' },
      { titulo: 'Inactivo', texto: 'Si deja el club, se desactiva desde "Editar": su historial se conserva.', permisos: ['alumnos.editar'] },
      { titulo: 'Eliminar', texto: 'La papelera de la ficha borra al alumno con toda su información (pagos, asistencia, rifas, documentos). No se puede deshacer: pide escribir su código para confirmar.', permisos: ['alumnos.eliminar'] },
    ],
  },
  'alumnos/inscripciones': {
    titulo: 'Cómo funcionan las inscripciones',
    intro: 'El valor, el plazo y los avisos se ajustan en Configuración.',
    pasos: [
      { titulo: 'Inscripción', texto: 'La hace el entrenador al registrar al alumno (o al renovarlo cada año). El valor y el plazo (por defecto $90.000 y 30 días) salen de la configuración del club.' },
      { titulo: 'Abonos', texto: 'Se aceptan pagos parciales dentro del plazo. Al completar el valor, la inscripción queda activa.' },
      { titulo: 'Prórroga', texto: 'Solo Admin o SuperAdmin, con motivo. Reactiva una inscripción rechazada por vencimiento.' },
      { titulo: 'Vencimiento', texto: 'Si el plazo termina sin completar el pago, el sistema la rechaza y avisa a la familia.' },
    ],
    nota: 'Un abono errado no se borra: el SuperAdmin lo anula (el motivo es opcional) y queda en el historial.',
  },
  rifas: {
    titulo: 'Cómo funcionan las rifas',
    pasos: [
      { titulo: 'Cuatro al año', texto: 'Cada rifa asigna un talonario a cada alumno inscrito: por defecto 20 puestos de $2.000, es decir $40.000 por talonario.' },
      { titulo: 'Talonario', texto: 'Es del alumno: sus boletas se leen con su código (F012-01 a F012-20). No hace falta anotar quién compró cada boleta.' },
      { titulo: 'Pagos', texto: 'El talonario se paga completo o por abonos. Un pago errado no se borra: el SuperAdmin lo anula (el motivo es opcional).' },
      { titulo: 'Paz y salvo', texto: 'El talonario está a paz y salvo cuando está pagado al 100 %. Si queda con saldo después de la fecha del sorteo, cuenta como deuda (y puede llevar a mora).' },
      { titulo: 'Sorteo', texto: 'Desde la fecha del sorteo, en la pestaña Sorteo. Solo participan los talonarios pagados al 100 %; se puede jugar varias veces.' },
      { titulo: 'Cancelar o eliminar', texto: 'Cancelar la deja visible como cancelada; eliminar la quita de todas las pantallas y de las deudas. Si ya tiene pagos, solo el SuperAdmin la puede eliminar.', permisos: ['rifas.gestionar'] },
    ],
  },
  'rifas/sorteo': {
    titulo: 'Cómo funciona el sorteo',
    pasos: [
      { titulo: 'La urna', texto: 'Solo entran las boletas de los talonarios pagados al 100 %. Cada talonario aporta todas sus boletas (por defecto 20).' },
      { titulo: 'La boleta', texto: 'Se lee como código del alumno y número de boleta: F012-07 es la boleta 7 del talonario de F012. El código lo asigna el sistema al registrar al alumno (F femenina, M masculina).' },
      { titulo: 'Jugar', texto: 'Desde la fecha del sorteo, el SuperAdmin presiona «Jugar la rifa»; se puede jugar otra vez (por ejemplo, para varios premios). Una boleta que ya ganó no vuelve a la urna. El servidor elige al azar; la pantalla solo muestra el giro.', permisos: ['sorteo.jugar'] },
      { titulo: 'Acta', texto: 'Cada jugada deja su acta con la boleta ganadora, el alumno dueño del talonario, cuántas boletas había y una huella que prueba que la lista no cambió. No se puede modificar.' },
      { titulo: 'Aviso', texto: '«Avisar por WhatsApp» abre el mensaje listo para el acudiente principal (o el alumno, si es mayor), para enviarlo desde el número del club.' },
    ],
  },
  multas: {
    titulo: 'Cómo funcionan las multas y la mora',
    pasos: [
      { titulo: 'Multa', texto: 'Se genera al cierre del día (11:59 pm) a quien no marcó ni avisó un entrenamiento. El valor es configurable (por defecto $2.000).' },
      { titulo: 'Pago', texto: 'Lo registran Admin o SuperAdmin. Una multa pagada no se anula.' },
      { titulo: 'Anular', texto: 'Una multa pendiente se puede anular (el motivo es opcional). Cancelar un entrenamiento anula sus multas pendientes.', permisos: ['multas.anular'] },
      { titulo: 'Mora', texto: 'Cualquier deuda (multas o talonarios de rifa) con más de 3 meses sin pagar pone la inscripción "en revisión". La familia recibe aviso antes.' },
      { titulo: 'Expulsión', texto: 'La confirma el SuperAdmin. Si el alumno paga mientras está en revisión por mora, vuelve solo a activa.', permisos: STAFF },
    ],
  },
  torneos: {
    titulo: 'Cómo funcionan los torneos',
    pasos: [
      { titulo: 'Torneos del club', texto: 'Los organiza el club y se inscriben clubes externos, no jugadores.' },
      { titulo: 'Cupo', texto: 'Cada torneo tiene un cupo de equipos. Si se llena, los nuevos quedan en lista de espera y entran solos cuando alguien se retira.' },
      { titulo: 'Pagos', texto: 'Cada equipo paga la inscripción fijada en el torneo; se aceptan abonos y queda confirmado al completar.' },
      { titulo: 'Entrenamientos', texto: 'Los días de torneo se cancelan los entrenamientos; si el torneo se cancela, vuelven.' },
    ],
  },
  'perfil-club': {
    titulo: 'Cómo funciona el perfil del club',
    pasos: [
      { titulo: 'Sitio público', texto: 'El sitio del club (proyecto aparte, «Ver sitio») toma de aquí el equipo, la galería, los videos, el contacto, la misión, visión e historia, y de Torneos los torneos abiertos. También muestra cifras totales del club. Nada privado de los alumnos sale allí.' },
      { titulo: 'Publicar', texto: 'El interruptor general y el de cada álbum, video e integrante deciden qué se ve. Con el general apagado, el sitio muestra solo su contenido fijo.' },
      { titulo: 'Fotos', texto: 'Se reducen a 1920 px y se les quitan los datos ocultos (como la ubicación del celular). Sube solo fotos con autorización de los acudientes de los menores que aparecen.' },
      { titulo: 'Torneos', texto: 'Los torneos con inscripciones abiertas aparecen en el sitio y los clubes externos se inscriben solos; quedan en Torneos marcados «desde el sitio» y te llega un aviso.' },
    ],
  },
  'perfil-club/equipo': {
    titulo: 'Cómo funciona el equipo técnico',
    pasos: [
      { titulo: 'En el sitio', texto: 'Cada entrenador aparece en «Nuestro equipo técnico» con su foto, cargo y presentación. El orden más bajo va primero.' },
      { titulo: 'Ocultar o quitar', texto: 'El interruptor lo oculta del sitio sin borrar nada; «Quitar» lo borra con su foto.' },
      { titulo: 'Foto', texto: 'Se recorta cuadrada y se le quitan los datos ocultos del celular. Mejor una foto de frente y con buena luz.' },
      { titulo: 'No es una cuenta', texto: 'Estos perfiles son solo para el sitio. Para que un entrenador entre a la plataforma, créale una cuenta en Usuarios.' },
    ],
  },
  asistente: {
    titulo: 'Cómo funciona el asistente',
    pasos: [
      { titulo: 'Pregunta normal', texto: 'Escribe como le preguntarías a alguien del club: "¿quién debe multas?", "¿cuánto le falta a F012 para estar a paz y salvo?". El asistente consulta los datos y responde.' },
      { titulo: 'Solo consulta', texto: 'No registra pagos ni cambia nada: te dice en qué pantalla hacerlo. Ve solo lo que tu cuenta puede ver.' },
      { titulo: 'Verifica', texto: 'Las respuestas las genera una IA y pueden equivocarse: confirma en la pantalla correspondiente antes de cobrar o decidir.' },
      { titulo: 'Privacidad', texto: 'La conversación no se guarda: se borra al recargar o al empezar una nueva. Nunca se envían documentos, teléfonos ni correos a la IA.' },
    ],
  },
  avisos: {
    titulo: 'Cómo funcionan los avisos',
    pasos: [
      { titulo: 'Sin costo', texto: 'Los correos salen solos. WhatsApp se envía a mano desde el número del club con un enlace listo (no se usan bots, para no arriesgar el bloqueo del número).' },
      { titulo: 'Cuándo se avisa', texto: 'Recordatorios de pago, inscripción vencida, multas y riesgo de mora.' },
    ],
  },
  configuracion: {
    titulo: 'Configuración del club',
    pasos: [
      { titulo: 'Parámetros', texto: 'Valor de la inscripción, plazo de pago, valor de la multa, meses para la mora, rifas por año y demás reglas.' },
      { titulo: 'Quién cambia', texto: 'Solo el SuperAdmin. Cada cambio queda en la auditoría y aplica a lo nuevo (lo ya creado conserva su valor).' },
    ],
  },
  usuarios: {
    titulo: 'Cuentas y roles',
    intro: 'Cada persona entra con su correo y su contraseña. Al crear una cuenta, la contraseña se muestra una sola vez para entregarla.',
    pasos: [
      { titulo: 'SuperAdmin', texto: 'El dueño y entrenador principal: acceso total.' },
      { titulo: 'Admin', texto: 'Gestiona alumnos, cobros, inscripciones y torneos.' },
      { titulo: 'Entrenador', texto: 'Asistente general (ambas ramas): alumnos, asistencia e inscripciones con abonos. No cobra multas ni rifas, no ve el documento completo ni cambia el horario.' },
      { titulo: 'Miembro', texto: 'Acudiente o alumno mayor de edad: solo consulta lo suyo. Al crear la cuenta se elige a qué alumno pertenece.' },
      { titulo: 'Contraseña', texto: 'La llave cambia la contraseña y cierra sus sesiones abiertas. Desactivar una cuenta le impide entrar sin borrar nada.' },
    ],
  },
};
