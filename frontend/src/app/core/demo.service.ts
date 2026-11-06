import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';

import type { Esquema } from './api/tipos';
import { API } from './modelos';

export type InfoDemo = Esquema<'DemoOut'>;

/**
 * ¿Es el demo público? La API lo dice en GET /demo (fuera del demo responde 404). Con eso la entrada muestra las
 * cuentas de prueba y el panel la franja «datos ficticios». Es solo presentación: lo que el demo no permite lo
 * bloquea el servidor.
 */
@Injectable({ providedIn: 'root' })
export class DemoService {
  private readonly http = inject(HttpClient);
  readonly info = signal<InfoDemo | null>(null);
  private pedido = false;

  cargar(): void {
    if (this.pedido) return;
    this.pedido = true;
    this.http.get<InfoDemo>(`${API}/demo`).subscribe({ next: (d) => this.info.set(d), error: () => undefined });
  }
}
