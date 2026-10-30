import { HttpErrorResponse, HttpInterceptorFn, HttpRequest } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, switchMap, throwError } from 'rxjs';

import { API } from '../modelos';
import { AuthService } from './auth.service';

/** Rutas de autenticación que no deben disparar una renovación (evita bucles). */
const SIN_RENOVAR = [`${API}/auth/login`, `${API}/auth/refresh`, `${API}/auth/logout`];

/**
 * Agrega el access token a las peticiones de NUESTRA API (nunca a otros dominios) y, si la respuesta es 401,
 * renueva la sesión una vez y reintenta. Si tampoco se puede renovar, manda al login.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  if (!req.url.startsWith(`${API}/`)) {
    return next(req);
  }
  const auth = inject(AuthService);
  const conToken = (r: HttpRequest<unknown>, token: string | null) =>
    token ? r.clone({ setHeaders: { Authorization: `Bearer ${token}` } }) : r;

  return next(conToken(req, auth.token())).pipe(
    catchError((error: unknown) => {
      const renovable =
        error instanceof HttpErrorResponse && error.status === 401 && !SIN_RENOVAR.includes(req.url);
      if (!renovable) {
        return throwError(() => error);
      }
      return auth.renovar().pipe(
        switchMap((token) => {
          if (!token) {
            auth.sesionExpirada();
            return throwError(() => error);
          }
          return next(conToken(req, token));
        }),
      );
    }),
  );
};
