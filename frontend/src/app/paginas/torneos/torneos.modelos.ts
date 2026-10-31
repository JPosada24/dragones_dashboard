import type { Esquema } from '../../core/api/tipos';

export type EstadoTorneo = Esquema<'TorneoOut'>['estado'];
export type EstadoEquipo = Esquema<'EquipoOut'>['estado'];
export type Torneo = Esquema<'TorneoOut'>;
export type PagoEquipo = Esquema<'PagoEquipoOut'>;
/** Club externo inscrito en un torneo (con los datos de su delegado). */
export type Equipo = Esquema<'EquipoOut'>;
export type Retiro = Esquema<'RetiroOut'>;
