import type { Esquema } from '../../core/api/tipos';

export type { EstadoCuenta } from '../resumen/resumen.modelos';
export type Rama = Esquema<'AlumnoOut'>['rama'];
export type AcudienteVinculado = Esquema<'AcudienteVinculadoOut'>;
export type Alumno = Esquema<'AlumnoOut'>;
export type Acudiente = Esquema<'AcudienteOut'>;
export type Documento = Esquema<'DocumentoOut'>;
export type RegistroHistorial = Esquema<'HistorialOut'>;
