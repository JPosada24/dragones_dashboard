import { HttpClient } from '@angular/common/http';
import { Observable, of, switchMap } from 'rxjs';

import { formatoFecha } from '../../compartido/fechas';
import { PesosPipe } from '../../compartido/pesos.pipe';
import { API } from '../../core/modelos';
import { Inscripcion } from './inscripciones.modelos';

/** Cómo paga la inscripción en el momento de inscribir. */
export type FormaPago = 'ninguno' | 'parcial' | 'completo';

export const inscripcionUrl = (id: string) => `${API}/inscripciones/${encodeURIComponent(id)}`;

/**
 * Inscribe al alumno en el año y, si se indicó, registra el primer abono con fecha `hoy`.
 * Lo usan Alumnos (al registrar o desde la ficha) e Inscripciones ("Nueva inscripción").
 * El abono solo se envía si quien inscribe puede abonar (`puedeAbonar`); el servidor lo verifica igual.
 */
export function inscribirConPago(
  http: HttpClient,
  alumnoId: string,
  pago: { forma: FormaPago; monto: number; hoy: string; puedeAbonar: boolean },
): Observable<Inscripcion> {
  return http.post<Inscripcion>(`${API}/inscripciones`, { alumno_id: alumnoId }).pipe(
    switchMap((i) => {
      const monto = pago.forma === 'completo' ? i.saldo : pago.forma === 'parcial' ? pago.monto : 0;
      if (!pago.puedeAbonar || monto <= 0 || i.saldo === 0) return of(i);
      return http.post<Inscripcion>(`${inscripcionUrl(i.id)}/pagos`, { fecha_pago: pago.hoy, monto });
    }),
  );
}

/** Qué falta en la forma de pago; null si está bien. */
export function problemaPago(forma: FormaPago, monto: number): string | null {
  if (forma !== 'parcial') return null;
  if (!Number.isInteger(monto) || monto < 1) return 'Escribe el valor del abono (en pesos, sin puntos).';
  return null;
}

const pesos = new PesosPipe();

/** "Abonó $40.000; saldo $50.000 hasta el 29/11/2026." o "La inscripción quedó paga y activa." */
export function resumenPago(i: Pick<Inscripcion, 'saldo' | 'monto_pagado' | 'fecha_limite_pago'>): string {
  if (i.saldo === 0) return 'La inscripción quedó paga y activa.';
  const pagado = i.monto_pagado ? `Abonó ${pesos.transform(i.monto_pagado)}; ` : '';
  return `${pagado}saldo ${pesos.transform(i.saldo)} hasta el ${formatoFecha(i.fecha_limite_pago)}.`;
}
