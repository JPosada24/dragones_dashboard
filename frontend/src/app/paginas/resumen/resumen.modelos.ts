import type { Esquema } from '../../core/api/tipos';

export type ResumenStaff = Esquema<'ResumenOut'>;
export type EstadoCuenta = Esquema<'EstadoCuentaOut'>;
/** Lo que la familia ve de cada hijo (subconjunto de AlumnoOut). */
export type AlumnoBasico = Pick<Esquema<'AlumnoOut'>, 'id' | 'nombres' | 'apellidos' | 'rama' | 'es_menor'>;
/** Próximos entrenamientos de la familia (subconjunto de SesionOut). */
export type SesionBasica = Pick<Esquema<'SesionOut'>, 'id' | 'fecha' | 'hora_inicio' | 'hora_fin' | 'lugar' | 'cancelada'>;
