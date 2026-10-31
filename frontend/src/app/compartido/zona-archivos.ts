import { ChangeDetectionStrategy, Component, ElementRef, input, output, signal, viewChild } from '@angular/core';

let siguienteId = 0;

/**
 * Campo para elegir archivos: se pueden arrastrar y soltar encima o tocar para abrir el selector.
 * Por dentro es un <input type="file"> real (accesible con teclado y lector de pantalla).
 *
 *   <app-zona-archivos accept="image/jpeg,image/png" [multiple]="true" (elegidos)="archivos = $event" />
 */
@Component({
  selector: 'app-zona-archivos',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <label class="zona" [class.encima]="encima()" [attr.for]="id"
           (dragenter)="arrastrando($event)" (dragover)="arrastrando($event)"
           (dragleave)="encima.set(false)" (drop)="soltar($event)">
      <span class="icono" aria-hidden="true">{{ multiple() ? 'add_photo_alternate' : 'image' }}</span>
      <span class="texto">
        @if (nombres().length) {
          <strong>{{ nombres().length === 1 ? nombres()[0] : nombres().length + ' archivos elegidos' }}</strong>
          <span class="nota">Arrastra otros o toca para cambiar</span>
        } @else {
          <strong>{{ multiple() ? 'Arrastra las fotos aquí' : 'Arrastra la foto aquí' }}</strong>
          <span class="nota">o toca para elegir{{ multiple() ? ' (puedes elegir varias)' : '' }}</span>
        }
      </span>
      <input #campo [id]="id" type="file" class="solo-lectores" [accept]="accept()" [multiple]="multiple()"
             [attr.aria-label]="etiqueta()" (change)="elegir($event)" />
    </label>
    @if (rechazados()) {
      <p class="rechazo" role="alert">{{ rechazados() }} {{ rechazados() === 1 ? 'archivo no es' : 'archivos no son' }} una imagen válida y no se agregó.</p>
    }
  `,
  styles: `
    :host { display: grid; gap: 6px; }
    .zona {
      display: flex; align-items: center; gap: 14px; padding: 18px 16px; cursor: pointer;
      border: 1.5px dashed var(--borde-fuerte); border-radius: var(--radio); background: var(--panel-hundido);
      transition: border-color 0.15s, background 0.15s;
    }
    .zona:hover, .zona:focus-within, .zona.encima { border-color: var(--naranja); background: var(--naranja-tenue); }
    .zona:focus-within { outline: 2px solid var(--naranja); outline-offset: 2px; }
    .icono { font-size: 30px; color: var(--naranja); }
    .texto { display: grid; gap: 2px; min-width: 0; }
    strong { font: 600 13px var(--f-texto); color: var(--texto); overflow-wrap: anywhere; }
    .nota { font-size: 11.5px; color: var(--texto-3); }
    .rechazo { margin: 0; font-size: 11.5px; color: var(--rojo); }
  `,
})
export class ZonaArchivos {
  readonly accept = input('image/jpeg,image/png,image/webp');
  readonly multiple = input(false);
  readonly etiqueta = input('Elegir archivos');
  readonly elegidos = output<File[]>();

  protected readonly id = `zona-archivos-${siguienteId++}`;
  protected readonly encima = signal(false);
  protected readonly nombres = signal<string[]>([]);
  protected readonly rechazados = signal(0);
  private readonly campo = viewChild.required<ElementRef<HTMLInputElement>>('campo');

  protected arrastrando(e: DragEvent): void {
    e.preventDefault(); // sin esto el navegador abriría la imagen en lugar de soltarla aquí
    if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
    this.encima.set(true);
  }

  protected soltar(e: DragEvent): void {
    e.preventDefault();
    this.encima.set(false);
    this.recibir(Array.from(e.dataTransfer?.files ?? []));
  }

  protected elegir(e: Event): void {
    this.recibir(Array.from((e.target as HTMLInputElement).files ?? []));
  }

  /** Solo se aceptan los tipos permitidos (el servidor vuelve a validar el contenido real). */
  private recibir(archivos: File[]): void {
    const tipos = this.accept().split(',').map((t) => t.trim());
    const validos = archivos.filter((f) => tipos.includes(f.type));
    const elegidos = this.multiple() ? validos : validos.slice(0, 1);
    this.rechazados.set(archivos.length - validos.length);
    this.nombres.set(elegidos.map((f) => f.name));
    if (!elegidos.length) this.campo().nativeElement.value = '';
    this.elegidos.emit(elegidos);
  }
}
