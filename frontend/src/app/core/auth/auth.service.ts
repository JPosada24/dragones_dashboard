import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, catchError, finalize, firstValueFrom, map, of, shareReplay, tap } from 'rxjs';

import { API, TokenOut, Usuario } from '../modelos';

/**
 * Sesión del usuario.
 *
 * - El access token (15 min) vive SOLO en memoria: nunca en localStorage/sessionStorage, que un script
 *   inyectado podría leer. Al recargar la página se recupera con el refresh token.
 * - El refresh token lo maneja el navegador en una cookie HttpOnly + SameSite=Strict que JavaScript no ve.
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);

  private readonly accessToken = signal<string | null>(null);
  readonly usuario = signal<Usuario | null>(null);
  readonly autenticado = computed(() => this.usuario() !== null);

  /** Renovación en curso: si varias peticiones reciben 401 a la vez, comparten una sola. */
  private renovando: Observable<string | null> | null = null;

  token(): string | null {
    return this.accessToken();
  }

  tiene(permiso: string): boolean {
    return this.usuario()?.permisos.includes(permiso) ?? false;
  }

  tieneAlguno(permisos: readonly string[]): boolean {
    return permisos.length === 0 || permisos.some((p) => this.tiene(p));
  }

  login(email: string, password: string): Observable<Usuario> {
    return this.http.post<TokenOut>(`${API}/auth/login`, { email, password }).pipe(
      tap((r) => this.guardar(r)),
      map((r) => r.usuario),
    );
  }

  /** Pide un access token nuevo con la cookie de refresh. Devuelve null si la sesión ya no es válida. */
  renovar(): Observable<string | null> {
    this.renovando ??= this.http.post<TokenOut>(`${API}/auth/refresh`, {}).pipe(
      tap((r) => this.guardar(r)),
      map((r) => r.access_token),
      catchError(() => {
        this.limpiar();
        return of(null);
      }),
      finalize(() => (this.renovando = null)),
      shareReplay(1),
    );
    return this.renovando;
  }

  /** Al abrir la app: si hay cookie de refresh válida, la sesión continúa sin pedir la clave. */
  async restaurarSesion(): Promise<void> {
    await firstValueFrom(this.renovar());
  }

  async logout(): Promise<void> {
    try {
      await firstValueFrom(this.http.post(`${API}/auth/logout`, {}));
    } catch {
      // Aunque falle la red, la sesión local se cierra igual.
    }
    this.limpiar();
    await this.router.navigate(['/login']);
  }

  /** Llamado por el interceptor cuando ni renovando se recupera la sesión. */
  sesionExpirada(): void {
    this.limpiar();
    void this.router.navigate(['/login'], { queryParams: { expirada: 1 } });
  }

  private guardar(r: TokenOut): void {
    this.accessToken.set(r.access_token);
    this.usuario.set(r.usuario);
  }

  private limpiar(): void {
    this.accessToken.set(null);
    this.usuario.set(null);
  }
}

/** Solo se aceptan rutas internas para volver tras el login (evita redirecciones abiertas a otros sitios). */
export function rutaSegura(volver: string | null | undefined): string {
  if (!volver || !volver.startsWith('/') || volver.startsWith('//') || volver.startsWith('/\\')) {
    return '/';
  }
  return volver;
}
