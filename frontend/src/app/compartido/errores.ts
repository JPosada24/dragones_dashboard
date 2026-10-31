import { HttpErrorResponse } from '@angular/common/http';

/** Texto para mostrar al usuario a partir de un error de la API (nunca detalles técnicos). */
export function mensajeError(e: unknown): string {
  if (!(e instanceof HttpErrorResponse)) return 'Ocurrió un error inesperado.';
  if (e.status === 0) return 'No hay conexión con el servidor. Intenta de nuevo.';
  if (e.status === 403) return 'No tienes permiso para hacer esto.';
  const detalle: unknown = e.error?.detail;
  if (e.status === 429) return typeof detalle === 'string' && detalle ? detalle : 'Demasiados intentos. Espera un momento.';
  if (typeof detalle === 'string' && detalle) return detalle;
  // Errores de validación de FastAPI: lista de {msg}.
  if (Array.isArray(detalle) && typeof detalle[0]?.msg === 'string') {
    return detalle[0].msg.replace(/^Value error, /, '');
  }
  if (e.status === 404) return 'No se encontró el registro.';
  return 'No se pudo completar la acción. Intenta de nuevo.';
}
