import type { Esquema } from '../../core/api/tipos';

export type EstadoTorneo = Esquema<'TorneoOut'>['estado'];
export type EstadoEquipo = Esquema<'EquipoOut'>['estado'];
export type Torneo = Esquema<'TorneoOut'>;
/** Un día del torneo para una rama, con sus sedes. */
export type Jornada = Esquema<'JornadaOut'>;
export type RamaTorneo = Jornada['rama'];
export type PagoEquipo = Esquema<'PagoEquipoOut'>;
/** Club externo inscrito en un torneo (con los datos de su delegado). */
export type Equipo = Esquema<'EquipoOut'>;
export type Retiro = Esquema<'RetiroOut'>;
/** Grupos de una rama (en borrador o publicados), con sus actas. */
export type SorteoGrupos = Esquema<'SorteoGruposOut'>;
export type EquipoGrupo = Esquema<'EquipoGrupoOut'>;
export type ActaGrupos = Esquema<'ActaGruposOut'>;
