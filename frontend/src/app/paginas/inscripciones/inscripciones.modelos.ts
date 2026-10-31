import type { Esquema } from '../../core/api/tipos';

export type EstadoInscripcion = Esquema<'InscripcionOut'>['estado'];
export type PagoInscripcion = Esquema<'PagoOut'>;
export type Prorroga = Esquema<'ProrrogaOut'>;
export type Inscripcion = Esquema<'InscripcionOut'>;
