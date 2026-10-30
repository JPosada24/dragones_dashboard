export type EstadoInscripcion = 'pendiente_pago' | 'activo' | 'a_expulsar' | 'expulsado' | 'rechazado';

export interface PagoInscripcion {
  id: string;
  fecha: string;
  monto: number; // negativo si es una anulación
  anula_id: string | null;
  anulado: boolean;
  motivo: string | null;
  registrado_por: string | null;
  creado_en: string;
}

export interface Prorroga {
  limite_anterior: string;
  limite_nuevo: string;
  motivo: string;
  concedida_por: string;
  creado_en: string;
}

export interface Inscripcion {
  id: string;
  alumno_id: string;
  alumno_nombre: string;
  anio: number;
  rama: 'masculina' | 'femenina';
  fecha_inscripcion: string;
  fecha_limite_pago: string;
  valor: number;
  fecha_pago: string | null;
  monto_pagado: number | null;
  saldo: number;
  estado: EstadoInscripcion;
  causa_rechazo: 'vencimiento' | 'manual' | null;
  causa_expulsion: 'mora' | 'manual' | null;
  motivo: string | null;
  prorrogas: Prorroga[];
  pagos: PagoInscripcion[];
}
