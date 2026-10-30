import {
  ChangeDetectionStrategy, Component, ElementRef, afterNextRender, input, output, viewChild,
} from '@angular/core';

let siguienteId = 0;

/**
 * Ventana emergente (popup) para formularios. Se muestra mientras exista: el padre la pone dentro de un @if.
 * Usa <dialog> nativo en modo modal: atrapa el foco, cierra con Escape y devuelve el foco al cerrar.
 *
 *   @if (editando()) {
 *     <app-dialogo titulo="Editar" (cerrar)="editando.set(false)"> …formulario… </app-dialogo>
 *   }
 */
@Component({
  selector: 'app-dialogo',
  template: `
    <dialog #dialogo [attr.aria-labelledby]="idTitulo" (cancel)="$event.preventDefault(); cerrar.emit()"
            (click)="clicFondo($event)">
      <div class="contenido">
        <header>
          <h2 [id]="idTitulo">{{ titulo() }}</h2>
          <button type="button" class="cerrar" (click)="cerrar.emit()" aria-label="Cerrar">
            <span class="icono" aria-hidden="true">close</span>
          </button>
        </header>
        @if (descripcion()) {
          <p class="descripcion">{{ descripcion() }}</p>
        }
        <ng-content />
      </div>
    </dialog>
  `,
  styleUrl: './dialogo.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Dialogo {
  readonly titulo = input.required<string>();
  readonly descripcion = input<string>('');
  readonly ancho = input<'normal' | 'ancho'>('normal');
  readonly cerrar = output<void>();

  protected readonly idTitulo = `dialogo-titulo-${siguienteId++}`;
  private readonly dialogo = viewChild.required<ElementRef<HTMLDialogElement>>('dialogo');

  constructor() {
    afterNextRender(() => {
      const d = this.dialogo().nativeElement;
      d.classList.toggle('ancho', this.ancho() === 'ancho');
      // jsdom (pruebas) no implementa showModal: allí basta con abrirlo.
      if (typeof d.showModal === 'function') d.showModal();
      else d.setAttribute('open', '');
    });
  }

  /** Un clic en el fondo oscuro (fuera del contenido) cierra la ventana. */
  protected clicFondo(e: MouseEvent): void {
    if (e.target === this.dialogo().nativeElement) this.cerrar.emit();
  }
}
