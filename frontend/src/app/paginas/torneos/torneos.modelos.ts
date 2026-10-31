export type EstadoTorneo = 'programado' | 'cancelado';
export type EstadoEquipo = 'confirmado' | 'pendiente_pago' | 'en_espera' | 'retirado';

export interface Torneo {
  id: string;
  nombre: string;
  rama: 'masculina' | 'femenina';
  fecha_inicio: string;
  fecha_fin: string;
  fecha_limite_inscripcion: string;
  lugar: string | null;
  cupo_equipos: number;
  valor_inscripcion: number;
  estado: EstadoTorneo;
  motivo_cancelacion: string | null;
  ocupados: number;
  confirmados: number;
  en_espera: number;
  recaudado: number;
}

export interface PagoEquipo {
  id: string;
  fecha: string;
  monto: number; // negativo si es una anulación
  anula_id: string | null;
  motivo: string | null;
  creado_en: string;
}

/** Club externo inscrito en un torneo (con los datos de su delegado). */
export interface Equipo {
  id: string;
  nombre_club: string;
  ciudad: string;
  delegado_nombre: string;
  delegado_telefono: string;
  delegado_email: string | null;
  estado: EstadoEquipo;
  valor: number;
  monto_pagado: number;
  saldo: number;
  motivo_retiro: string | null;
  origen?: 'staff' | 'sitio';
  pagos: PagoEquipo[];
}

export interface Retiro {
  retirado: Equipo;
  promovido: Equipo | null;
}
