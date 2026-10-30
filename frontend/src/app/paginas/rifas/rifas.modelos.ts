export type EstadoRifa = 'abierta' | 'sorteada' | 'cancelada';

export interface Rifa {
  id: string;
  nombre: string;
  anio: number;
  numero: number; // 1.ª, 2.ª… del año
  premio: string;
  fecha_sorteo: string;
  puestos_por_talonario: number;
  precio_puesto: number;
  valor_talonario: number;
  estado: EstadoRifa;
  motivo_cancelacion: string | null;
  talonarios: number;
  talonarios_pagados: number;
  recaudado: number;
  esperado: number;
}

export interface PagoPuesto {
  id: string;
  fecha: string;
  monto: number; // negativo si es una anulación
  anula_id: string | null;
  motivo: string | null;
  creado_en: string;
}

export interface Puesto {
  numero: number; // número interno del puesto en la rifa (el que usa la API)
  boleta: number; // 1…20 dentro del talonario
  comprador_nombre: string | null;
  comprador_telefono: string | null;
  monto_pagado: number;
  saldo: number;
  pagos: PagoPuesto[];
}

export interface Talonario {
  id: string;
  alumno_id: string;
  alumno_nombre: string;
  rama: string;
  codigo: string; // F012: con el número de boleta forma la boleta F012-07
  desde: number;
  hasta: number;
  recaudado: number;
  saldo: number;
  pagado: boolean;
  puestos: Puesto[];
}

export interface Acta {
  rifa_id: string;
  numero_ganador: number;
  codigo: string;
  boleta: number;
  alumno_id: string;
  alumno_nombre: string;
  rama: string;
  comprador_nombre: string | null;
  total_participantes: number;
  participantes: number[];
  huella: string;
  jugado_en: string;
}

/** Fila de la matriz de paz y salvo: un alumno y su talonario en cada rifa del año. */
export interface FilaPazYSalvo {
  alumno_id: string;
  codigo: string;
  alumno_nombre: string;
  rama: string;
  celdas: (Talonario | null)[]; // en el orden de las rifas; null = sin talonario en esa rifa
  deuda: number;
}
