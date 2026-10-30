/** Textos de los estados que llegan de la API (para no repetirlos en cada pantalla). */

export const ESTADO_INSCRIPCION: Record<string, string> = {
  pendiente_pago: 'Pendiente de pago',
  activo: 'Activa',
  a_expulsar: 'En revisión',
  expulsado: 'Expulsado',
  rechazado: 'Rechazada',
};

export const TIPOS_DOCUMENTO: { valor: string; texto: string }[] = [
  { valor: 'RC', texto: 'Registro civil' },
  { valor: 'TI', texto: 'Tarjeta de identidad' },
  { valor: 'CC', texto: 'Cédula de ciudadanía' },
  { valor: 'CE', texto: 'Cédula de extranjería' },
  { valor: 'PA', texto: 'Pasaporte' },
  { valor: 'PPT', texto: 'Permiso por protección temporal' },
];
