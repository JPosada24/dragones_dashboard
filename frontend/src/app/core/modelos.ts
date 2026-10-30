/** Tipos que devuelve la API (backend FastAPI). */

export type Rol = 'SUPERADMIN' | 'ADMIN' | 'ENTRENADOR' | 'MIEMBRO';

export interface Usuario {
  id: string;
  email: string;
  nombre: string;
  rol: Rol;
  activo: boolean;
  permisos: string[];
}

export interface TokenOut {
  access_token: string;
  token_type: 'bearer';
  expires_in: number;
  usuario: Usuario;
}

export interface Notificacion {
  id: string;
  tipo: string;
  titulo: string;
  mensaje: string;
  alumno_id: string | null;
  leida: boolean;
  creado_en: string;
}

export const NOMBRE_ROL: Record<Rol, string> = {
  SUPERADMIN: 'SuperAdmin',
  ADMIN: 'Admin',
  ENTRENADOR: 'Entrenador',
  MIEMBRO: 'Miembro',
};

/** Todas las rutas de la API pasan por el mismo origen (proxy en desarrollo, Caddy en producción). */
export const API = '/api/v1';
