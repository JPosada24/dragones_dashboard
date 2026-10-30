/** Tipos de la API de asistencia (/sesiones, /justificaciones). */

export type Rama = 'masculina' | 'femenina';
export type EstadoAsistencia = 'presente' | 'ausente' | 'justificado';
export type Marca = 'presente' | 'ausente';

export interface Sesion {
  id: string;
  rama: Rama;
  fecha: string; // AAAA-MM-DD
  hora_inicio: string; // HH:MM:SS
  hora_fin: string;
  lugar: string | null;
  cancelada: boolean;
  motivo_cancelacion: string | null;
  cerrada: boolean;
}

export interface FilaPlanilla {
  alumno_id: string;
  alumno_nombre: string;
  asistencia: EstadoAsistencia | null;
  justificacion: 'pendiente' | 'aprobada' | 'rechazada' | null;
  multa: 'pendiente' | 'pagada' | null;
}

export interface Justificacion {
  id: string;
  sesion_id: string;
  fecha_sesion: string;
  rama: Rama;
  alumno_id: string;
  alumno_nombre: string;
  motivo: string;
  estado: 'pendiente' | 'aprobada' | 'rechazada';
  comentario: string | null;
  creado_en: string;
  revisada_en: string | null;
}

export interface AlertaInasistencia {
  alumno_id: string;
  alumno_nombre: string;
  rama: Rama;
  inasistencias_seguidas: number;
}
