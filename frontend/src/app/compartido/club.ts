/** Tipos del perfil del club (panel y sitio público) y utilidades para mostrarlo. */
import type { Esquema } from '../core/api/tipos';

export type PerfilClub = Esquema<'PerfilOut'>;
export type FotoClub = Esquema<'FotoOut'>;
/** `portada`: versión de la portada propia; null = se usa la primera foto. */
export type AlbumClub = Esquema<'AlbumOut'>;
export type VideoClub = Esquema<'VideoOut'>;
/** `foto`: versión de la foto; null = sin foto. */
export type IntegranteClub = Esquema<'IntegranteOut'>;
/** Torneo ya jugado del sitio. `anuncio`: versión del afiche; null = sin anuncio. */
export type TorneoRealizadoClub = Esquema<'TorneoRealizadoOut'>;

/**
 * Lo que identifica a cada video lo valida el servidor; aquí se vuelve a comprobar antes de armar un enlace, que
 * siempre usa el dominio fijo de su red.
 */
const RUTAS_VIDEO: Record<VideoClub['plataforma'], { forma: RegExp; base: string; nombre: string }> = {
  youtube: { forma: /^[A-Za-z0-9_-]{11}$/, base: 'https://www.youtube.com/watch?v=', nombre: 'YouTube' },
  tiktok: { forma: /^@[A-Za-z0-9._]{2,24}\/video\/\d{8,25}$/, base: 'https://www.tiktok.com/', nombre: 'TikTok' },
  instagram: { forma: /^(p|reel|tv)\/[A-Za-z0-9_-]{5,40}$/, base: 'https://www.instagram.com/', nombre: 'Instagram' },
};

export function enlaceVideo(v: Pick<VideoClub, 'plataforma' | 'ruta'>): string | null {
  const p = RUTAS_VIDEO[v.plataforma];
  return p?.forma.test(v.ruta) ? p.base + v.ruta : null;
}

/** Portada del video: solo YouTube la da sin pedir permiso; los demás se muestran con el nombre de su red. */
export function miniaturaVideo(v: Pick<VideoClub, 'plataforma' | 'ruta'>): string | null {
  return v.plataforma === 'youtube' && RUTAS_VIDEO.youtube.forma.test(v.ruta)
    ? `https://i.ytimg.com/vi/${v.ruta}/mqdefault.jpg` : null;
}

export function nombrePlataforma(v: Pick<VideoClub, 'plataforma'>): string {
  return RUTAS_VIDEO[v.plataforma]?.nombre ?? 'Video';
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
