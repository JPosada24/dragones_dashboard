/** Tipos del perfil del club (panel y sitio público) y utilidades para mostrarlo. */
export interface PerfilClub {
  nombre: string;
  lema: string | null;
  ciudad: string | null;
  sede: string | null;
  fundado_en: number | null;
  formacion_intro: string | null;
  formacion: Etapa[] | null;
  mision: string | null;
  vision: string | null;
  historia: string | null;
  whatsapp: string | null;
  correo: string | null;
  instagram: string | null;
  facebook: string | null;
  publicado: boolean;
}

export interface FotoClub {
  id: string;
  ancho: number;
  alto: number;
}

export interface AlbumClub {
  id: string;
  nombre: string;
  fecha: string | null;
  publicado: boolean;
  fotos: FotoClub[];
}

export interface VideoClub {
  id: string;
  titulo: string;
  youtube_id: string;
  publicado: boolean;
}

export interface IntegranteClub {
  id: string;
  nombre: string;
  cargo: string;
  bio: string | null;
  orden: number;
  publicado: boolean;
  foto: string | null; // versión de la foto; null = sin foto
}

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
export interface Etapa {
  titulo: string;
  texto: string;
}

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
