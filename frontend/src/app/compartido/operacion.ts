import { signal } from '@angular/core';
import { Observable } from 'rxjs';

import { mensajeError } from './errores';

export interface Mensaje {
  error: boolean;
  texto: string;
}

/**
 * Estado de las acciones de una pantalla: si hay una petición en curso, el aviso general (`<app-aviso>`) y el
 * error dentro del popup abierto. Todas las pantallas lo comparten para que se comporten igual.
 *
 * Regla: el error de una acción hecha desde un popup se muestra **dentro** del popup (así no se pierde lo escrito);
 * el de una acción directa (un botón de la página) va al aviso general.
 */
export class Operacion {
  readonly ocupado = signal(false);
  readonly mensaje = signal<Mensaje | null>(null);
  readonly errorDialogo = signal<string | null>(null);

  /** Abre un popup limpiando los mensajes anteriores. */
  abrir(mostrar: () => void): void {
    this.errorDialogo.set(null);
    this.mensaje.set(null);
    mostrar();
  }

  /** Ejecuta la petición marcando "ocupado"; si falla, el error va al popup o al aviso general. */
  ejecutar<T>(peticion: Observable<T>, ok: (r: T) => void, { enDialogo = true }: { enDialogo?: boolean } = {}): void {
    this.ocupado.set(true);
    this.errorDialogo.set(null);
    if (!enDialogo) this.mensaje.set(null);
    peticion.subscribe({
      next: (r) => {
        this.ocupado.set(false);
        ok(r);
      },
      error: (e: unknown) => {
        this.ocupado.set(false);
        if (enDialogo) this.errorDialogo.set(mensajeError(e));
        else this.error(e);
      },
    });
  }

  exito(texto: string): void {
    this.mensaje.set({ error: false, texto });
  }

  error(e: unknown): void {
    this.mensaje.set({ error: true, texto: mensajeError(e) });
  }
}
