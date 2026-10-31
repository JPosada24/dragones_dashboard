/** Tipos del perfil del club (panel y sitio público) y utilidades para mostrarlo. */
import type { Esquema } from '../core/api/tipos';

export type PerfilClub = Esquema<'PerfilOut'>;
export type FotoClub = Esquema<'FotoOut'>;
/** `portada`: versión de la portada propia; null = se usa la primera foto. */
export type AlbumClub = Esquema<'AlbumOut'>;
export type VideoClub = Esquema<'VideoOut'>;
/** `foto`: versión de la foto; null = sin foto. */
export type IntegranteClub = Esquema<'IntegranteOut'>;

/** El id de YouTube lo valida el servidor; aquí se vuelve a comprobar antes de armar cualquier enlace. */
const ID_YOUTUBE = /^[A-Za-z0-9_-]{11}$/;

export function miniaturaYoutube(id: string): string | null {
  return ID_YOUTUBE.test(id) ? `https://i.ytimg.com/vi/${id}/mqdefault.jpg` : null;
}

export function enlaceYoutube(id: string): string | null {
  return ID_YOUTUBE.test(id) ? `https://www.youtube.com/watch?v=${id}` : null;
}

/** Iniciales para el avatar: "Ana María Ruiz" → "AR". */
export function iniciales(nombre: string): string {
  const partes = nombre.trim().split(/\s+/).filter(Boolean);
  const primera = partes[0]?.[0] ?? '';
  const ultima = partes.length > 1 ? (partes[partes.length - 1]?.[0] ?? '') : '';
  return (primera + ultima).toUpperCase();
}

/** Una etapa de «La formación va por rotaciones»: su zona es la posición en la lista (1 a 6). */
export type Etapa = Esquema<'EtapaIn'>;

/** Etapas que muestra el sitio mientras nadie las edite en el panel (zona 1 a 6). */
export const ETAPAS_BASE: Etapa[] = [
  { titulo: 'Primer contacto', texto: 'Reglas básicas, control de pelota, primer paso.' },
  { titulo: 'Técnica individual', texto: 'Gesto del golpe, saque y recepción.' },
  { titulo: 'Juego en la red', texto: 'Colocación, ataque y bloqueo con compañero.' },
  { titulo: 'Sistema de juego', texto: 'Defensa, transición y jugadas de equipo construidas.' },
  { titulo: 'Competencia', texto: 'Torneos municipales y del departamento.' },
  { titulo: 'Jugador completo', texto: 'Valores, disciplina y pertenencia al club.' },
];

export const INTRO_BASE =
  'Este es el diagrama de una rotación de voleibol y también el camino del jugador en el club: ' +
  'se entra por la zona 1 y se sale con el juego completo.';

/** Zonas en el orden en que se ven en la cancha: arriba 4·3·2 (junto a la red), abajo 5·6·1. */
export const ORDEN_CANCHA = [4, 3, 2, 5, 6, 1];
