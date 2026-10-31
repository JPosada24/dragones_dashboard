/** Tipos que devuelve la API (generados del contrato OpenAPI del backend FastAPI). */
import type { Esquema } from './api/tipos';

export type Usuario = Esquema<'UsuarioOut'>;
export type Rol = Usuario['rol'];
export type TokenOut = Esquema<'TokenOut'>;
export type Notificacion = Esquema<'NotificacionOut'>;

export const NOMBRE_ROL: Record<Rol, string> = {
  SUPERADMIN: 'SuperAdmin',
  ADMIN: 'Admin',
  ENTRENADOR: 'Entrenador',
  MIEMBRO: 'Miembro',
};

/** Todas las rutas de la API pasan por el mismo origen (proxy en desarrollo, Caddy en producción). */
export const API = '/api/v1';
