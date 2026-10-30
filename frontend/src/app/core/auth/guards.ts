import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { AuthService } from './auth.service';

/**
 * Los guards solo ordenan la navegación. La autorización real la hace SIEMPRE el servidor:
 * ocultar una pantalla aquí no da ni quita permisos.
 */
export const requiereSesion: CanActivateFn = (_ruta, estado) => {
  const auth = inject(AuthService);
  if (auth.autenticado()) {
    return true;
  }
  return inject(Router).createUrlTree(['/login'], { queryParams: { volver: estado.url } });
};

export const soloInvitado: CanActivateFn = () => {
  return inject(AuthService).autenticado() ? inject(Router).createUrlTree(['/']) : true;
};

/** Exige al menos uno de los permisos de `data.permisos` de la ruta. */
export const requierePermiso: CanActivateFn = (ruta) => {
  const permisos = (ruta.data['permisos'] as string[] | undefined) ?? [];
  return inject(AuthService).tieneAlguno(permisos) ? true : inject(Router).createUrlTree(['/']);
};
