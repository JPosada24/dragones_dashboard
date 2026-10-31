import type { Esquema } from '../../core/api/tipos';

export type EstadoMulta = Esquema<'MultaOut'>['estado'];
export type Multa = Esquema<'MultaOut'>;
/** Deuda vencida de un alumno (multas y talonarios) y cuándo entra o entró en mora. */
export type SituacionMora = Esquema<'SituacionOut'>;

/** Multas pendientes de un alumno, para cobrarlas juntas (se arma en el navegador). */
export interface GrupoMultas {
  alumno_id: string;
  alumno_nombre: string;
  rama: string;
  multas: Multa[];
  total: number;
}
