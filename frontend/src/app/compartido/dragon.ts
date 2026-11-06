import { ChangeDetectionStrategy, Component, input } from '@angular/core';

import type { Pose } from '../core/tutorial.service';

let siguienteId = 0;

/**
 * Brasa, el dragón del club: busto en 3/4 al estilo de las mascotas deportivas (ilustración vectorial propia).
 * Tres poses: saluda (garra con el balón), señala (garra apuntando) y remata (balón en llamas y rugido).
 * Es decorativo: el texto de la burbuja dice lo mismo, así que el lector de pantalla lo ignora.
 */
@Component({
  selector: 'app-dragon',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '[attr.data-pose]': 'pose()' },
  template: `
    <svg viewBox="0 0 200 200" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient [attr.id]="'piel-' + id" x1="0" y1="0" x2="0.35" y2="1">
          <stop offset="0" class="c-naranja-claro" />
          <stop offset="0.55" class="c-naranja" />
          <stop offset="1" class="c-naranja-oscuro" />
        </linearGradient>
        <linearGradient [attr.id]="'cuerno-' + id" x1="1" y1="1" x2="0" y2="0">
          <stop offset="0" class="c-oro" />
          <stop offset="1" class="c-hueso" />
        </linearGradient>
        <linearGradient [attr.id]="'pecho-' + id" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" class="c-oro" />
          <stop offset="1" class="c-naranja" />
        </linearGradient>
        <radialGradient [attr.id]="'ojo-' + id" cx="0.4" cy="0.45" r="0.7">
          <stop offset="0" class="c-blanco" />
          <stop offset="0.35" class="c-oro" />
          <stop offset="1" class="c-naranja" />
        </radialGradient>
        <radialGradient [attr.id]="'balon-' + id" cx="0.35" cy="0.3" r="0.8">
          <stop offset="0" class="c-blanco" />
          <stop offset="1" class="c-gris" />
        </radialGradient>
      </defs>

      <g class="dragon">
        <!-- Cuernos largos hacia atrás -->
        <path [attr.fill]="url('cuerno')" class="borde" d="M68 40 C 52 14, 32 2, 4 -4 C 28 14, 40 30, 50 54 Z" />
        <path [attr.fill]="url('cuerno')" class="borde" d="M46 64 C 28 50, 12 48, -6 56 C 14 58, 26 66, 40 80 Z" />
        <path class="estria" d="M50 30 l-6 5 M40 22 l-5 5 M30 15 l-5 4 M30 56 l-3 6 M20 54 l-2 6" />

        <!-- Cuello en S con púas en la nuca y placas en el pecho -->
        <path class="borde puas" d="M44 112 L20 116 L40 100 Z M38 138 L14 146 L36 124 Z M34 166 L10 176 L34 152 Z" />
        <path [attr.fill]="url('piel')" class="borde" d="M54 100 C 40 128, 34 162, 30 200 L 118 200 C 112 170, 104 142, 98 116 Z" />
        <path [attr.fill]="url('pecho')" class="borde" d="M80 116 C 90 142, 98 170, 100 200 L 118 200 C 112 170, 104 142, 98 116 Z" />
        <path class="placa" d="M86 132 L 102 130 M91 150 L 107 148 M95 168 L 111 167 M98 186 L 114 185" />
        <path class="escama" d="M46 150 q6 -5 12 0 M52 172 q6 -5 12 0 M40 190 q6 -5 12 0 M60 132 q6 -5 12 0 M66 160 q6 -5 12 0" />

        @if (pose() === 'remata') {
          <g class="remate">
            <path [attr.fill]="url('piel')" class="borde" d="M128 200 L 150 130 Q 160 96 170 70 L 186 74 Q 180 104 170 136 L 160 200 Z" />
            <path class="escama" d="M146 170 q6 -5 12 0 M154 140 q6 -5 12 0" />
          </g>
        }

        <!-- Cabeza -->
        <path class="borde puas" d="M50 98 L24 108 L46 86 Z M44 84 L20 86 L42 72 Z" />
        <g class="mandibula">
          <path [attr.fill]="url('piel')" class="borde" d="M108 100 L 136 102 L 178 104 L 170 118 L 130 128 L 88 124 Z" />
          <path class="diente" d="M138 104 l3 -8 l3 8 Z M151 105 l3 -8 l3 8 Z M163 105 l3 -9 l3 9 Z" />
        </g>
        <path class="boca" d="M106 98 L 188 80 L 180 106 L 108 104 Z" />
        <path [attr.fill]="url('piel')" class="borde" d="M40 72 Q 46 44 70 34 L 112 30 Q 138 32 158 46 L 186 58 Q 196 64 192 76 L 180 84 L 140 90 L 116 98 L 88 112 Q 60 110 48 96 Q 38 84 40 72 Z" />
        <path class="borde puas" d="M78 36 L 84 22 L 92 34 Z M96 32 L 104 18 L 110 32 Z" />
        <!-- Luz sobre el hocico, sombra en la mejilla y línea de la mejilla -->
        <path class="luz" d="M74 38 L 112 34 Q 136 36 156 50 L 182 62 L 154 56 Q 132 46 104 46 Z" />
        <path class="sombra" d="M48 94 Q 62 108 88 110 L 112 98 L 88 96 Q 66 94 50 82 Z" />
        <path class="estria" d="M60 88 Q 80 96 104 92 M70 64 q 10 -3 18 2" />
        <path class="diente" d="M128 93 l3 10 l3 -10.5 Z M141 90.5 l3 10 l3 -10.5 Z M154 88 l3 11 l3 -11.5 Z M167 85.5 l3 9 l3 -9.5 Z" />
        <path class="colmillo" d="M115 96 l5 17 l4 -18 Z" />
        <!-- Ojo encendido bajo una ceja pesada -->
        <path class="brillo-ojo" d="M94 62 L 120 48 L 144 56 L 120 70 Z" />
        <path [attr.fill]="url('ojo')" class="borde-fino" d="M98 62 L 120 51 L 140 57 L 119 68 Z" />
        <path class="pupila" d="M119 52.5 L 122.6 59.5 L 119 66.8 L 115.8 59.5 Z" />
        <path class="ceja" d="M84 52 L 148 42 L 134 54 L 100 60 Z" />
        <path class="fosa" d="M180 64 l8 4" />

        @switch (pose()) {
          @case ('remata') {
            <!-- Balón en llamas tras el remate (el antebrazo va detrás de la cabeza) -->
            <g class="remate">
              <path class="llama" d="M158 30 C 152 14, 162 6, 166 -6 C 170 6, 176 8, 180 -2 C 184 8, 188 12, 188 0 C 198 14, 200 26, 194 36 Z" />
              <path class="llama-centro" d="M164 30 C 162 20, 168 14, 170 6 C 174 14, 178 16, 182 10 C 188 20, 188 28, 186 34 Z" />
              <g transform="translate(176 40) scale(0.769)">
                <circle r="26" [attr.fill]="url('balon')" class="borde" />
                <path class="gajo" d="M-25.4 -4 C -11 1, 8 -3, 24 -11 A26 26 0 0 0 -25.4 -4 Z" />
                <path class="gajo" d="M7 -25 C 19 -12, 23 4, 18 18.6 A26 26 0 0 0 7 -25 Z" />
                <path class="costura" d="M-25.4 -4 C -11 1, 8 -3, 24 -11 M-7 -25 C -12 -8, -6 9, 8 24.6 M7 -25 C 19 -12, 23 4, 18 18.6" />
              </g>
            </g>
          }
          @default {
            <!-- La garra sostiene el balón (al señalar, una uña apunta) -->
            <path [attr.fill]="url('piel')" class="borde" d="M108 200 C 110 186, 118 176, 130 172 L 146 192 C 140 194, 136 198, 136 200 Z" />
            <ellipse [attr.fill]="url('piel')" class="borde" cx="134" cy="178" rx="17" ry="13" />
            <g transform="translate(156 160) scale(1.000)">
                <circle r="26" [attr.fill]="url('balon')" class="borde" />
                <path class="gajo" d="M-25.4 -4 C -11 1, 8 -3, 24 -11 A26 26 0 0 0 -25.4 -4 Z" />
                <path class="gajo" d="M7 -25 C 19 -12, 23 4, 18 18.6 A26 26 0 0 0 7 -25 Z" />
                <path class="costura" d="M-25.4 -4 C -11 1, 8 -3, 24 -11 M-7 -25 C -12 -8, -6 9, 8 24.6 M7 -25 C 19 -12, 23 4, 18 18.6" />
              </g>
            <path class="garra" d="M140 168 Q 140 157 149 151 Q 146 160 146 169 Z M146 178 Q 150 167 160 163 Q 155 172 152 180 Z M150 188 Q 158 181 168 181 Q 161 187 156 192 Z" />
            @if (pose() === 'senala') {
              <path class="garra" d="M150 186 L 196 172 L 152 194 Z" />
            }
          }
        }
        @if (pose() !== 'remata') {
          <g class="humo">
            <circle cx="194" cy="58" r="3.5" />
            <circle cx="199" cy="48" r="2.5" />
          </g>
        }
      </g>
    </svg>
  `,
  styles: `
    :host {
      display: block;
      width: 96px;
      height: 96px;
    }

    svg {
      width: 100%;
      height: 100%;
      overflow: visible;
    }

    .c-naranja-claro { stop-color: var(--naranja); stop-opacity: 1; }
    .c-naranja { stop-color: var(--naranja); }
    .c-naranja-oscuro { stop-color: var(--rojo-oscuro); }
    .c-oro { stop-color: var(--oro); }
    .c-hueso { stop-color: var(--texto); }
    .c-blanco { stop-color: var(--texto-blanco); }
    .c-gris { stop-color: var(--texto-2); }

    .borde,
    .borde-fino {
      stroke: var(--fondo);
      stroke-width: 3;
      stroke-linejoin: round;
    }
    .borde-fino { stroke-width: 1.5; }

    .puas { fill: var(--naranja-oscuro); }
    .placa,
    .escama,
    .estria { fill: none; stroke: var(--fondo); stroke-linecap: round; }
    .placa { stroke-width: 2.2; opacity: 0.55; }
    .escama { stroke-width: 1.8; opacity: 0.35; }
    .estria { stroke-width: 2; opacity: 0.45; }
    .luz { fill: var(--oro); opacity: 0.35; }
    .sombra { fill: var(--fondo); opacity: 0.3; }
    .boca { fill: var(--fondo); stroke: var(--fondo); stroke-width: 3; stroke-linejoin: round; }
    .diente,
    .colmillo { fill: var(--texto); stroke: var(--fondo); stroke-width: 1.2; stroke-linejoin: round; }
    .brillo-ojo { fill: var(--oro); opacity: 0.45; filter: blur(3px); }
    .pupila { fill: var(--fondo); }
    .ceja { fill: var(--rojo-oscuro); stroke: var(--fondo); stroke-width: 2.5; stroke-linejoin: round; }
    .fosa { fill: none; stroke: var(--fondo); stroke-width: 3; stroke-linecap: round; }
    .garra { fill: var(--texto); stroke: var(--fondo); stroke-width: 2; stroke-linejoin: round; }
    .costura { fill: none; stroke: var(--fondo); stroke-width: 2; stroke-linecap: round; }
    .gajo { fill: var(--oro); }
    .llama-centro { fill: var(--oro); }
    .llama { fill: var(--naranja); stroke: var(--oro); stroke-width: 2; stroke-linejoin: round; }
    .humo circle { fill: var(--texto-3); opacity: 0.5; }

    /* Movimiento sobrio: respira, humo que sube y, al rematar, el balón vibra */
    .dragon { transform-box: view-box; transform-origin: 90px 200px; animation: respirar 3.2s ease-in-out infinite; }
    .humo { animation: humear 2.6s ease-out infinite; }
    .mandibula { transform-box: view-box; transform-origin: 108px 102px; }
    :host([data-pose='remata']) .mandibula { transform: rotate(9deg); }
    .remate { transform-box: view-box; transform-origin: 150px 200px; animation: rematar 0.8s ease-in-out infinite alternate; }

    @keyframes respirar { 50% { transform: scale(1.012) translateY(-1px); } }
    @keyframes humear { from { opacity: 0.7; transform: translate(0, 0); } to { opacity: 0; transform: translate(4px, -10px); } }
    @keyframes rematar { to { transform: rotate(-3deg); } }

    @media (prefers-reduced-motion: reduce) {
      .dragon,
      .humo,
      .remate { animation: none; }
    }
  `,
})
export class Dragon {
  readonly pose = input<Pose>('saluda');
  /** Ids únicos de los degradados (por si hubiera más de un dragón en la página). */
  protected readonly id = `dragon-${siguienteId++}`;

  protected url(nombre: string): string {
    return `url(#${nombre}-${this.id})`;
  }
}
