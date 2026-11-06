import { ChangeDetectionStrategy, Component, input } from '@angular/core';

import type { Pose } from '../core/tutorial.service';

/**
 * Brasa, el dragón del club (ilustración propia, vectorial). Tres poses: saluda, señala y remata el balón.
 * Es decorativo: el texto de la burbuja dice lo mismo, así que el lector de pantalla lo ignora.
 */
@Component({
  selector: 'app-dragon',
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '[attr.data-pose]': 'pose()' },
  template: `
    <svg viewBox="0 0 160 160" aria-hidden="true" focusable="false">
      <g class="dragon">
        <!-- Cola con punta de lanza -->
        <path class="trazo-borde" d="M56 128 C 34 138, 18 126, 20 108 C 21 98, 14 92, 9 95" />
        <path class="trazo-cuerpo" d="M56 128 C 34 138, 18 126, 20 108 C 21 98, 14 92, 9 95" />
        <path class="pua" d="M10 96 L0 84 L15 86 L13 99 Z" />

        <!-- Alas -->
        <path class="ala" d="M62 94 L30 50 L38 72 L20 66 L36 86 L18 88 L44 102 Z" />
        <path class="ala" d="M96 92 L130 48 L124 70 L142 64 L128 84 L146 86 L118 100 Z" />
        <path class="hueso" d="M62 94 L30 50 M58 96 L20 66 M54 99 L18 88 M96 92 L130 48 M100 94 L142 64 M106 97 L146 86" />

        <!-- Patas -->
        <ellipse class="cuerpo" cx="62" cy="140" rx="13" ry="8" />
        <ellipse class="cuerpo" cx="97" cy="140" rx="13" ry="8" />
        <path class="garra" d="M52 145 l3 5 l3 -5z M58 146 l3 5 l3 -5z M64 146 l3 5 l3 -5z M88 146 l3 5 l3 -5z M94 146 l3 5 l3 -5z M100 145 l3 5 l3 -5z" />

        <!-- Cuerpo, púas del lomo y panza -->
        <path class="pua" d="M51 94 L38 90 L48 82 Z M47 108 L34 108 L45 99 Z M48 122 L36 126 L44 114 Z" />
        <ellipse class="cuerpo" cx="79" cy="112" rx="31" ry="30" />
        <ellipse class="panza" cx="82" cy="117" rx="18" ry="21" />
        <path class="placa" d="M67 106 Q82 101 97 106 M65 116 Q82 111 99 116 M67 126 Q82 122 97 126" />

        <!-- Brazo de atrás: sostiene el balón (o queda abajo al rematar) -->
        @if (pose() === 'remata') {
          <g class="remate">
            <path class="trazo-borde brazo" d="M64 100 Q 38 94 34 60" />
            <path class="trazo-cuerpo brazo" d="M64 100 Q 38 94 34 60" />
            <path class="garra" d="M29 60 l-1 -8 l5 5z M34 58 l1 -8 l4 7z" />
            <g class="balon" transform="translate(24 38)">
              <circle r="13" />
              <path class="gajo" d="M-12.4 -4 Q0 3 12.6 -3.4 A13 13 0 0 0 -12.4 -4 Z" />
              <path class="costura" d="M-12.4 -4 Q0 3 12.6 -3.4 M-5 -12 Q-1 1 5 12 M6 -11.5 Q13 -1 9.5 9" />
            </g>
            <path class="velocidad" d="M10 18 l-7 -6 M6 34 l-7 0 M9 50 l-7 5" />
          </g>
        } @else {
          <g class="balon" transform="translate(44 124)">
            <circle r="13" />
            <path class="gajo" d="M-12.4 -4 Q0 3 12.6 -3.4 A13 13 0 0 0 -12.4 -4 Z" />
            <path class="costura" d="M-12.4 -4 Q0 3 12.6 -3.4 M-5 -12 Q-1 1 5 12 M6 -11.5 Q13 -1 9.5 9" />
          </g>
          <path class="trazo-borde brazo" d="M66 102 Q 50 106 52 122" />
          <path class="trazo-cuerpo brazo" d="M66 102 Q 50 106 52 122" />
          <path class="garra" d="M50 121 l-5 3 l5 2z M53 124 l-3 5 l5 0z" />
        }

        <!-- Cabeza -->
        <path class="cuerno" d="M62 38 Q 50 20 34 14 Q 46 30 52 46 Z" />
        <path class="cuerno" d="M80 30 Q 74 10 60 2 Q 80 8 94 30 Z" />
        <path class="cuerpo" d="M48 62 C 46 40, 64 28, 84 28 C 104 28, 118 38, 122 52 C 134 54, 140 64, 136 74 C 132 84, 118 86, 104 84 C 88 88, 66 88, 56 80 C 50 75, 48 69, 48 62 Z" />
        <path class="pua" d="M50 52 L40 46 L50 42 Z M49 66 L38 64 L48 58 Z" />
        <ellipse class="ojo" cx="80" cy="57" rx="8" ry="8.5" />
        <ellipse class="ojo" cx="102" cy="55" rx="7" ry="8" />
        <ellipse class="pupila" cx="82" cy="58" rx="2" ry="6" />
        <ellipse class="pupila" cx="104" cy="56" rx="1.8" ry="5.6" />
        <circle class="brillo" cx="78.5" cy="53" r="1.6" />
        <circle class="brillo" cx="100.5" cy="51" r="1.4" />
        <!-- Cejas en V: cara de competidor -->
        <path class="ceja" d="M68 44 L90 51 M95 50 L114 41" />
        <ellipse class="pupila" cx="128" cy="63" rx="2.2" ry="1.6" />
        <ellipse class="pupila" cx="134" cy="65" rx="2" ry="1.5" />

        @if (pose() === 'remata') {
          <!-- Rugido con llamarada -->
          <path class="boca-abierta" d="M100 74 Q 118 94 136 72 Q 118 80 100 74 Z" />
          <path class="colmillo" d="M106 76 l3 6 l3 -5z M123 78 l3 -6 l3 5z" />
          <path class="llama" d="M136 72 C 148 62, 152 70, 160 60 C 157 76, 150 84, 136 78 Z" />
          <path class="llama-centro" d="M138 74 C 146 70, 149 73, 154 68 C 151 77, 146 79, 138 77 Z" />
        } @else {
          <path class="boca" d="M100 76 Q 116 82 132 74" />
          <path class="colmillo" d="M107 78 l3 7 l3 -6z M121 78.5 l2.5 6 l3 -6.5z" />
          <g class="humo">
            <circle cx="142" cy="56" r="3" />
            <circle cx="148" cy="49" r="2.2" />
          </g>
        }

        <!-- Brazo de adelante: saluda, señala o remata -->
        @switch (pose()) {
          @case ('saluda') {
            <g class="brazo-saludo">
              <path class="trazo-borde brazo" d="M96 104 Q 142 106 148 72" />
              <path class="trazo-cuerpo brazo" d="M96 104 Q 142 106 148 72" />
              <path class="garra" d="M143 72 l0 -8 l4 6z M148 70 l2 -8 l3 7z M152 73 l5 -6 l0 8z" />
            </g>
          }
          @case ('senala') {
            <path class="trazo-borde brazo" d="M96 104 Q 114 106 132 98" />
            <path class="trazo-cuerpo brazo" d="M96 104 Q 114 106 132 98" />
            <path class="garra" d="M132 94 l10 3 l-10 4z" />
          }
          @case ('remata') {
            <!-- Puño cerrado de celebración -->
            <path class="trazo-borde brazo" d="M96 104 Q 116 110 112 124" />
            <path class="trazo-cuerpo brazo" d="M96 104 Q 116 110 112 124" />
            <circle class="cuerpo" cx="112" cy="126" r="5.5" />
          }
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

    .cuerpo,
    .pua,
    .ala,
    .cuerno,
    .ojo,
    .panza,
    .balon circle,
    .boca-abierta,
    .colmillo,
    .garra {
      stroke: var(--fondo);
      stroke-width: 2.5;
      stroke-linejoin: round;
    }

    .cuerpo { fill: var(--naranja); }
    .ala { fill: var(--naranja-oscuro); }
    .hueso { fill: none; stroke: var(--fondo); stroke-width: 1.6; stroke-linecap: round; opacity: 0.55; }
    .pua,
    .cuerno { fill: var(--oro); }
    .panza { fill: var(--oro); stroke-width: 0; }
    .placa { fill: none; stroke: var(--naranja-oscuro); stroke-width: 2; stroke-linecap: round; }
    .ojo { fill: var(--oro); stroke-width: 2; }
    .pupila { fill: var(--fondo); }
    .brillo { fill: var(--texto-blanco); }
    .ceja { fill: none; stroke: var(--fondo); stroke-width: 5; stroke-linecap: round; }
    .boca { fill: none; stroke: var(--fondo); stroke-width: 3; stroke-linecap: round; }
    .boca-abierta { fill: var(--fondo); }
    .colmillo,
    .garra { fill: var(--texto-blanco); stroke-width: 1.4; }
    .llama { fill: var(--naranja); }
    .llama-centro { fill: var(--oro); }
    .humo circle { fill: var(--texto-3); opacity: 0.45; }
    .velocidad { fill: none; stroke: var(--oro); stroke-width: 3; stroke-linecap: round; }

    .trazo-borde,
    .trazo-cuerpo { fill: none; stroke-linecap: round; }
    .trazo-borde { stroke: var(--fondo); stroke-width: 15; }
    .trazo-cuerpo { stroke: var(--naranja); stroke-width: 9.5; }
    .trazo-borde.brazo { stroke-width: 13; }
    .trazo-cuerpo.brazo { stroke-width: 8; }

    .balon circle { fill: var(--texto-blanco); }
    .gajo { fill: var(--oro); }
    .costura { fill: none; stroke: var(--fondo); stroke-width: 1.6; stroke-linecap: round; }

    /* Movimiento suave: flota, saluda, el humo sube y el balón vibra al rematar */
    .dragon { animation: flotar 2.8s ease-in-out infinite; }
    .brazo-saludo { transform-box: view-box; transform-origin: 96px 104px; animation: saludar 1.1s ease-in-out infinite; }
    .humo { animation: humear 2.4s ease-out infinite; }
    .remate { transform-box: view-box; transform-origin: 64px 100px; animation: rematar 0.9s ease-in-out infinite alternate; }

    @keyframes flotar { 50% { transform: translateY(-3px); } }
    @keyframes saludar { 50% { transform: rotate(-12deg); } }
    @keyframes humear { from { opacity: 0.7; transform: translateY(0); } to { opacity: 0; transform: translateY(-8px); } }
    @keyframes rematar { to { transform: rotate(6deg); } }

    @media (prefers-reduced-motion: reduce) {
      .dragon,
      .brazo-saludo,
      .humo,
      .remate { animation: none; }
    }
  `,
})
export class Dragon {
  readonly pose = input<Pose>('saluda');
}
