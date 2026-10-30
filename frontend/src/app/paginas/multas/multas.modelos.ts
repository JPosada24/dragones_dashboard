export type EstadoMulta = 'pendiente' | 'pagada' | 'anulada';

export interface Multa {
  id: string;
  alumno_id: string;
  alumno_nombre: string;
  rama: 'masculina' | 'femenina';
  sesion_id: string;
  fecha_sesion: string;
  valor: number;
  estado: EstadoMulta;
  fecha_pago: string | null;
  motivo_anulacion: string | null;
}

/** Deuda vencida de un alumno (multas y talonarios) y cuándo entra o entró en mora. */
export interface SituacionMora {
  alumno_id: string;
  alumno_nombre: string;
  rama: 'masculina' | 'femenina';
  total_vencido: number;
  vencida_desde: string;
  entra_en_mora: string;
  en_mora: boolean;
  deudas: { concepto: string; monto: number; vence: string }[];
}

/** Multas pendientes de un alumno, para cobrarlas juntas. */
export interface GrupoMultas {
  alumno_id: string;
  alumno_nombre: string;
  rama: string;
  multas: Multa[];
  total: number;
}
