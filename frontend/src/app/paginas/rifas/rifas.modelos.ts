import type { Esquema } from '../../core/api/tipos';

export type EstadoRifa = Esquema<'RifaOut'>['estado'];
export type Rifa = Esquema<'RifaOut'>;
export type PagoTalonario = Esquema<'PagoTalonarioOut'>;
/** Talonario de un alumno: sus boletas se leen código-número (F012-01 … F012-20). */
export type Talonario = Esquema<'TalonarioOut'>;
/** Una jugada del sorteo (una rifa se puede jugar varias veces). */
export type Acta = Esquema<'ActaOut'>;

/** Fila de la matriz de paz y salvo: un alumno y su talonario en cada rifa del año (se arma en el navegador). */
export interface FilaPazYSalvo {
  alumno_id: string;
  codigo: string;
  alumno_nombre: string;
  rama: string;
  celdas: (Talonario | null)[]; // en el orden de las rifas; null = sin talonario en esa rifa
  deuda: number;
}
