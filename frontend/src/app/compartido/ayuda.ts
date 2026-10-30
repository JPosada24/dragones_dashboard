import { ChangeDetectionStrategy, Component, computed, inject, input, signal } from '@angular/core';

import { AuthService } from '../core/auth/auth.service';
import { Dialogo } from './dialogo';

/** Explicación de una pantalla: pasos o reglas, y una nota final. Texto plano (nunca HTML). */
export interface Ayuda {
  titulo: string;
  intro?: string;
  pasos: { titulo: string; texto: string; permisos?: string[] }[]; // permisos: solo se muestra a quien tenga uno
  nota?: string;
}

/**
 * Botón "?" que abre la explicación de la pantalla en un popup. Lo pone el marco junto al título de cada
 * vista; el contenido sale de `core/secciones.ts`.
 */
@Component({
  selector: 'app-ayuda',
  imports: [Dialogo],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <button type="button" class="ayuda" (click)="abierta.set(true)" [attr.aria-label]="ayuda().titulo"
            title="Cómo funciona">
      <span class="icono" aria-hidden="true">help</span>
    </button>
    @if (abierta()) {
      <app-dialogo [titulo]="ayuda().titulo" [descripcion]="ayuda().intro ?? ''" (cerrar)="abierta.set(false)">
        <div class="formulario">
          <ol class="pasos">
            @for (p of pasos(); track p.titulo) {
              <li><b>{{ p.titulo }}.</b> {{ p.texto }}</li>
            }
          </ol>
          @if (ayuda().nota) {
            <p class="nota-ayuda">{{ ayuda().nota }}</p>
          }
          <div class="acciones">
            <button type="button" class="boton chico" (click)="abierta.set(false)">Entendido</button>
          </div>
        </div>
      </app-dialogo>
    }
  `,
  styles: `
    :host {
      display: inline-flex;
    }

    .ayuda {
      width: 24px;
      height: 24px;
      display: grid;
      place-items: center;
      padding: 0;
      border: 1px solid var(--borde-fuerte);
      border-radius: 50%;
      background: transparent;
      color: var(--texto-3);
      cursor: pointer;

      .icono {
        font-size: 16px;
      }

      &:hover {
        border-color: var(--oro);
        color: var(--oro);
      }
    }

    .pasos {
      margin: 0;
      padding-left: 18px;
      display: grid;
      gap: 10px;
      font: 400 12.5px/1.55 var(--f-texto);
      color: var(--texto-2);

      b {
        color: var(--texto);
      }

      li::marker {
        font: 600 11px var(--f-mono);
        color: var(--naranja);
      }
    }

    .nota-ayuda {
      font-size: 11.5px;
      line-height: 1.5;
      color: var(--texto-3);
    }
  `,
})
export class AyudaBoton {
  private readonly auth = inject(AuthService);

  readonly ayuda = input.required<Ayuda>();
  protected readonly abierta = signal(false);

  protected readonly pasos = computed(() =>
    this.ayuda().pasos.filter((p) => !p.permisos || this.auth.tieneAlguno(p.permisos)),
  );
}
