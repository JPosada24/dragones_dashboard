import { ChangeDetectionStrategy, Component } from '@angular/core';
import { IsActiveMatchOptions, RouterLink, RouterLinkActive } from '@angular/router';

/** Pestañas de la sección Alumnos: las fichas (personas) y sus inscripciones del año (matrícula y pagos). */
@Component({
  selector: 'app-pestanas-alumnos',
  imports: [RouterLink, RouterLinkActive],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <nav class="pestanas" aria-label="Vistas de alumnos">
      <a routerLink="/alumnos" routerLinkActive="activa" [routerLinkActiveOptions]="soloFichas" ariaCurrentWhenActive="page">
        <span class="icono" aria-hidden="true">badge</span> Fichas
      </a>
      <a routerLink="/alumnos/inscripciones" routerLinkActive="activa" ariaCurrentWhenActive="page">
        <span class="icono" aria-hidden="true">receipt_long</span> Inscripciones y pagos
      </a>
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
export class PestanasAlumnos {
  /** /alumnos?id=… sigue siendo la pestaña de fichas. */
  protected readonly soloFichas: IsActiveMatchOptions = {
    paths: 'exact', queryParams: 'ignored', fragment: 'ignored', matrixParams: 'ignored',
  };
}
