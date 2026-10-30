import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { IsActiveMatchOptions, RouterLink, RouterLinkActive } from '@angular/router';

export interface Pestana {
  ruta: string; // absoluta: '/alumnos'
  texto: string;
  icono: string; // Material Symbols
}

/** Pestañas de una sección con varias vistas (Alumnos: fichas / inscripciones; Rifas: talonarios / sorteo). */
@Component({
  selector: 'app-pestanas',
  imports: [RouterLink, RouterLinkActive],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <nav class="pestanas" [attr.aria-label]="etiqueta()">
      @for (p of pestanas(); track p.ruta) {
        <a [routerLink]="p.ruta" routerLinkActive="activa" [routerLinkActiveOptions]="exacta" ariaCurrentWhenActive="page">
          <span class="icono" aria-hidden="true">{{ p.icono }}</span> {{ p.texto }}
        </a>
      }
    </nav>
  `,
  styles: `
    .pestanas {
      display: flex;
      gap: 4px;
      border-bottom: 1px solid var(--borde);
      overflow-x: auto;
    }

    a {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      padding: 9px 14px;
      margin-bottom: -1px;
      border-bottom: 2px solid transparent;
      color: var(--texto-3);
      font: 600 12.5px var(--f-texto);
      text-decoration: none;
      white-space: nowrap;

      .icono {
        font-size: 18px;
      }

      &:hover {
        color: var(--texto);
      }

      &.activa {
        color: var(--texto-blanco);
        border-bottom-color: var(--naranja);

        .icono {
          color: var(--naranja);
        }
      }
    }
  `,
})
export class Pestanas {
  readonly pestanas = input.required<Pestana[]>();
  readonly etiqueta = input('Vistas');

  /** Cada pestaña es activa solo en su ruta exacta (con o sin parámetros como ?id=…). */
  protected readonly exacta: IsActiveMatchOptions = {
    paths: 'exact', queryParams: 'ignored', fragment: 'ignored', matrixParams: 'ignored',
  };
}

export const PESTANAS_ALUMNOS: Pestana[] = [
  { ruta: '/alumnos', texto: 'Fichas', icono: 'badge' },
  { ruta: '/alumnos/inscripciones', texto: 'Inscripciones y pagos', icono: 'receipt_long' },
];

export const PESTANAS_RIFAS: Pestana[] = [
  { ruta: '/rifas', texto: 'Rifas y talonarios', icono: 'confirmation_number' },
  { ruta: '/rifas/sorteo', texto: 'Sorteo', icono: 'casino' },
];
