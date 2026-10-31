/** Tipos de la API de asistencia (/sesiones, /justificaciones), generados del contrato OpenAPI. */
import type { Esquema } from '../../core/api/tipos';

export type Rama = Esquema<'FilaPlanillaOut'>['rama'];
export type EstadoAsistencia = Esquema<'HistorialOut'>['estado'];
/** Lo que el staff marca en la planilla (P/A/J). */
export type Marca = EstadoAsistencia;

/** Entrenamiento general del club (ambas ramas). */
export type Sesion = Esquema<'SesionOut'>;
export type DiaHorario = Esquema<'DiaHorarioOut'>;
export type Horario = Esquema<'HorarioOut'>;
export type HorarioActualizado = Esquema<'HorarioActualizadoOut'>;
export type FilaPlanilla = Esquema<'FilaPlanillaOut'>;
export type Justificacion = Esquema<'JustificacionOut'>;
export type AlertaInasistencia = Esquema<'AlertaOut'>;
