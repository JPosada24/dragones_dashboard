/** Utilidades de fechas "de calendario" (sin hora), en la zona local del navegador. */

/** AAAA-MM-DD, como las espera la API. */
export function isoLocal(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/** Convierte AAAA-MM-DD en una fecha local (sin el corrimiento de zona de `new Date('AAAA-MM-DD')`). */
export function desdeIso(iso: string): Date {
  const [a = 0, m = 1, d = 1] = iso.split('-').map(Number);
  return new Date(a, m - 1, d);
}

export function sumarDias(d: Date, dias: number): Date {
  const r = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  r.setDate(r.getDate() + dias);
  return r;
}

/** Lunes de la semana de `d` (la semana va de lunes a domingo). */
export function lunesDe(d: Date): Date {
  return sumarDias(d, -diaSemana(d));
}

/** 0 = lunes … 6 = domingo (como la API). */
export function diaSemana(d: Date): number {
  return (d.getDay() + 6) % 7;
}
