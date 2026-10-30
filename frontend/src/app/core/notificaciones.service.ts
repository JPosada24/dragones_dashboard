import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';

import { API, Notificacion } from './modelos';

/** Bandeja de avisos del usuario (los suyos; el servidor no devuelve los de otros). */
@Injectable({ providedIn: 'root' })
export class NotificacionesService {
  private readonly http = inject(HttpClient);
  readonly noLeidas = signal(0);

  listar(soloNoLeidas = false): Observable<Notificacion[]> {
    return this.http.get<Notificacion[]>(`${API}/notificaciones/mias`, {
      params: { no_leidas: soloNoLeidas, limit: 100 },
    });
  }

  actualizarConteo(): void {
    this.listar(true).subscribe({ next: (l) => this.noLeidas.set(l.length), error: () => undefined });
  }

  marcarLeida(id: string): Observable<Notificacion> {
    return this.http
      .post<Notificacion>(`${API}/notificaciones/${encodeURIComponent(id)}/leer`, {})
      .pipe(tap(() => this.noLeidas.update((n) => Math.max(0, n - 1))));
  }

  marcarTodas(): Observable<{ marcadas: number }> {
    return this.http
      .post<{ marcadas: number }>(`${API}/notificaciones/mias/leer-todas`, {})
      .pipe(tap(() => this.noLeidas.set(0)));
  }
}
