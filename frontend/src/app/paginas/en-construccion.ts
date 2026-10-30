import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/** Pantalla provisional: la sección existe en el menú pero su interfaz llega en la siguiente entrega. */
@Component({
  selector: 'app-en-construccion',
  template: `
    <section class="panel caja">
      <span class="icono" aria-hidden="true">construction</span>
      <div>
        <h2>En construcción</h2>
        <p>{{ descripcion() }}</p>
        <p class="nota">Mientras tanto, todo esto ya funciona en la API (<span class="mono">/api/docs</span>).</p>
      </div>
    </section>
  `,
  styles: `
    .caja { display: flex; gap: 16px; padding: 22px; align-items: flex-start; }
    .icono { font-size: 30px; color: var(--oro); }
    h2 { font: 600 15px var(--f-titulo); color: var(--texto-blanco); }
    p { margin: 6px 0 0; color: var(--texto-2); line-height: 1.5; }
    .nota { font-size: 12px; color: var(--texto-3); }
  `,
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class EnConstruccionPage {
  /** Llega desde los datos de la ruta (withComponentInputBinding). */
  readonly descripcion = input('');
}
