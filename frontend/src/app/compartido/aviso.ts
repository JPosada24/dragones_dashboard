import { ChangeDetectionStrategy, Component, effect, input, output } from '@angular/core';

/**
 * Mensaje de resultado ("Sesión cancelada", un error de la API...) con botón para cerrarlo.
 * Los de éxito se cierran solos tras `duracion` ms; los errores se quedan hasta que el usuario
 * los cierre, para que no se pierdan antes de leerlos.
 */
@Component({
  selector: 'app-aviso',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="mensaje" [class.error]="error()" [attr.role]="error() ? 'alert' : 'status'">
      <span class="texto">{{ texto() }}</span>
      <button type="button" class="cerrar" aria-label="Cerrar mensaje" (click)="cerrar.emit()">
        <span class="icono" aria-hidden="true">close</span>
      </button>
    </div>
  `,
  styles: `
    :host {
      display: block;
    }

    .mensaje {
      display: flex;
      align-items: center;
      gap: 10px;
      padding-right: 6px;
    }

    .texto {
      flex: 1;
      min-width: 0;
      overflow-wrap: anywhere;
    }

    .cerrar {
      flex: none;
      display: grid;
      place-items: center;
      width: 26px;
      height: 26px;
      padding: 0;
      border: 0;
      border-radius: 5px;
      background: transparent;
      color: inherit;
      cursor: pointer;

      &:hover {
        background: rgba(255, 255, 255, 0.08);
      }

      .icono {
        font-size: 17px;
      }
    }
  `,
})
export class Aviso {
  readonly texto = input.required<string>();
  readonly error = input(false);
  /** Milisegundos antes de cerrarse solo (0 = no se cierra solo). Los errores nunca se cierran solos. */
  readonly duracion = input(6000);
  readonly cerrar = output<void>();

  constructor() {
    effect((alLimpiar) => {
      this.texto(); // un texto nuevo reinicia la cuenta
      const ms = this.duracion();
      if (this.error() || ms <= 0) return;
      const t = setTimeout(() => this.cerrar.emit(), ms);
      alLimpiar(() => clearTimeout(t));
    });
  }
}
