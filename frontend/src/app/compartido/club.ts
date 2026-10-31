/** Tipos del perfil del club (panel y sitio público) y utilidades para mostrarlo. */
export interface PerfilClub {
  nombre: string;
  lema: string | null;
  ciudad: string | null;
  sede: string | null;
  fundado_en: number | null;
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
