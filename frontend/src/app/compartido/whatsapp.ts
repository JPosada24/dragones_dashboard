/** Número de WhatsApp para wa.me: solo dígitos; los celulares colombianos de 10 dígitos llevan el 57. */
export function numeroWhatsApp(telefono: string | null): string | null {
  const digitos = (telefono ?? '').replace(/\D/g, '');
  if (digitos.length === 10 && digitos.startsWith('3')) return `57${digitos}`;
  return digitos.length >= 11 && digitos.length <= 15 ? digitos : null;
}
