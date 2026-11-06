import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import type { Pose } from '../core/tutorial.service';

/** Imagen de cada pose (WebP con transparencia, ~50 KB, servida por el propio panel: la CSP no deja cargar de afuera). */
const IMAGEN: Record<Pose, { src: string; ancho: number; alto: number }> = {
  saluda: { src: 'brasa/saluda.webp', ancho: 397, alto: 512 },
  senala: { src: 'brasa/senala.webp', ancho: 415, alto: 512 },
  remata: { src: 'brasa/remata.webp', ancho: 512, alto: 366 },
};

/**
 * Kiira, el dragón del club, en estilo de animación 3D. Tres poses: saluda, señala y remata.
 * Es decorativo (alt vacío): el texto de la burbuja dice lo mismo. Se mueve suave y se queda quieto con
 * «reducir movimiento».
 */
@Component({
  selector: 'app-dragon',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '[attr.data-pose]': 'pose()' },
  template: `
    @let i = imagen();
    <img [src]="i.src" alt="" [attr.width]="i.ancho" [attr.height]="i.alto" decoding="async" draggable="false" />
  `,
  styles: `
    :host {
      display: block;
      width: 96px;
      height: 96px;
    }

    img {
      display: block;
      width: 100%;
      height: 100%;
      object-fit: contain;
      object-position: bottom center;
      filter: drop-shadow(0 6px 10px rgba(0, 0, 0, 0.45));
      transform-origin: 50% 100%;
      animation: respirar 3.2s ease-in-out infinite;
      user-select: none;
    }

    /* Al cambiar de pose entra con un pequeño salto; al rematar, salta de verdad. */
    :host([data-pose='senala']) img { animation: entrar 0.35s ease-out, respirar 3.2s ease-in-out 0.35s infinite; }
    :host([data-pose='remata']) img { animation: saltar 0.9s ease-in-out infinite; }

    @keyframes respirar { 50% { transform: translateY(-2px) scale(1.015); } }
    @keyframes entrar { from { transform: translateY(6px) scale(0.96); opacity: 0.6; } }
    @keyframes saltar {
      0%, 100% { transform: translateY(0) scale(1, 1); }
      30% { transform: translateY(0) scale(1.04, 0.95); }
      60% { transform: translateY(-12px) scale(0.98, 1.03); }
    }

    @media (prefers-reduced-motion: reduce) {
      img,
      :host([data-pose]) img { animation: none; }
    }
  `,
})
export class Dragon {
  readonly pose = input<Pose>('saluda');
  protected readonly imagen = computed(() => IMAGEN[this.pose()]);
}
