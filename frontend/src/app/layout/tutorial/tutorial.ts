import { DOCUMENT } from '@angular/common';
import {
  ChangeDetectionStrategy, Component, ElementRef, afterRenderEffect, inject, signal, viewChild,
} from '@angular/core';

import { Dragon } from '../../compartido/dragon';
import { TutorialService } from '../../core/tutorial.service';

const MARGEN = 16;
const ANCHO = 340;

interface Caja { top: number; left: number; width: number; height: number; }

/**
 * Recorrido guiado: oscurece el panel, resalta el elemento del paso (`data-tutorial="…"`) y muestra la burbuja de
 * Brasa al lado. Es un <dialog> modal: atrapa el foco, Escape lo salta y el resto del panel queda inerte.
 * Si el elemento no está a la vista (p. ej. el menú lateral en el celular), la burbuja va al centro.
 */
@Component({
  selector: 'app-tutorial',
  imports: [Dragon],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { '(window:resize)': 'medir()' },
  template: `
    @if (tutorial.activo() && tutorial.paso(); as p) {
      <!-- Las flechas pasan de paso: el foco siempre está en un botón de la burbuja, dentro del diálogo. -->
      <!-- eslint-disable-next-line @angular-eslint/template/interactive-supports-focus -->
      <dialog #dialogo class="tutorial" aria-labelledby="tutorial-titulo" aria-describedby="tutorial-texto"
              (cancel)="$event.preventDefault(); tutorial.terminar()" (keydown)="tecla($event)">
        @if (foco(); as f) {
          <div class="foco" [style.top.px]="f.top" [style.left.px]="f.left" [style.width.px]="f.width"
               [style.height.px]="f.height"></div>
        } @else {
          <div class="velo"></div>
        }
        <div #burbuja class="burbuja" [class.centro]="!foco()" [style.top.px]="posicion().top"
             [style.left.px]="posicion().left">
          <app-dragon [pose]="p.pose" />
          <div class="texto">
            <p class="progreso mono">{{ tutorial.indice() + 1 }} de {{ tutorial.pasos().length }}</p>
            <h2 id="tutorial-titulo">{{ p.titulo }}</h2>
            <p id="tutorial-texto">{{ p.texto }}</p>
            <div class="acciones">
              @if (tutorial.indice() < tutorial.pasos().length - 1) {
                <button type="button" class="saltar" (click)="tutorial.terminar()">Saltar</button>
              }
              <span class="crece"></span>
              @if (tutorial.indice() > 0) {
                <button type="button" class="boton secundario chico" (click)="tutorial.anterior()">Atrás</button>
              }
              <button #siguiente type="button" class="boton chico" (click)="tutorial.siguiente()">
                {{ tutorial.indice() === tutorial.pasos().length - 1 ? '¡Listo!' : 'Siguiente' }}
              </button>
            </div>
          </div>
        </div>
      </dialog>
    }
  `,
  styleUrl: './tutorial.scss',
})
export class Tutorial {
  protected readonly tutorial = inject(TutorialService);
  private readonly doc = inject(DOCUMENT);
  private readonly dialogo = viewChild<ElementRef<HTMLDialogElement>>('dialogo');
  private readonly burbuja = viewChild<ElementRef<HTMLElement>>('burbuja');
  private readonly botonSiguiente = viewChild<ElementRef<HTMLButtonElement>>('siguiente');

  /** Recuadro resaltado alrededor del elemento del paso (null = no hay elemento a la vista). */
  protected readonly foco = signal<Caja | null>(null);
  protected readonly posicion = signal({ top: 0, left: 0 });

  constructor() {
    // Cada vez que cambia el paso: abre el diálogo (una vez), mide el elemento y pasa el foco a «Siguiente».
    afterRenderEffect(() => {
      const paso = this.tutorial.paso();
      const d = this.dialogo()?.nativeElement;
      if (!paso || !d) return;
      if (!d.open) {
        // jsdom (pruebas) no implementa showModal: allí basta con abrirlo.
        if (typeof d.showModal === 'function') d.showModal();
        else d.setAttribute('open', '');
      }
      this.medir();
      requestAnimationFrame(() => this.medir()); // ya con el alto real de la burbuja de este paso
      this.botonSiguiente()?.nativeElement.focus();
    });
  }

  /** Elemento visible con ese `data-tutorial` (el del menú lateral o el de las pestañas del celular). */
  private objetivo(clave: string | null): HTMLElement | null {
    if (!clave) return null;
    const candidatos = [...this.doc.querySelectorAll<HTMLElement>(`[data-tutorial="${CSS.escape(clave)}"]`)];
    return candidatos.find((e) => {
      const r = e.getBoundingClientRect();
      return r.width > 0 && r.height > 0;
    }) ?? null;
  }

  protected medir(): void {
    const paso = this.tutorial.paso();
    if (!paso) return;
    const vw = this.doc.documentElement.clientWidth || window.innerWidth;
    const vh = window.innerHeight;
    const ancho = Math.min(ANCHO, vw - 2 * MARGEN);
    const alto = this.burbuja()?.nativeElement.offsetHeight || 200;
    const el = this.objetivo(paso.objetivo);
    if (!el) {
      this.foco.set(null);
      this.posicion.set({ top: Math.max(MARGEN, (vh - alto) / 2), left: Math.max(MARGEN, (vw - ancho) / 2) });
      return;
    }
    const r = el.getBoundingClientRect();
    this.foco.set({ top: r.top - 6, left: r.left - 6, width: r.width + 12, height: r.height + 12 });
    const limitar = (v: number, max: number) => Math.min(Math.max(MARGEN, v), Math.max(MARGEN, max));
    if (r.right + 16 + ancho <= vw - MARGEN) {
      // A la derecha (el menú lateral del escritorio).
      this.posicion.set({ left: r.right + 16, top: limitar(r.top + r.height / 2 - alto / 2, vh - alto - MARGEN) });
    } else if (r.bottom + 12 + alto <= vh - MARGEN) {
      this.posicion.set({ top: r.bottom + 12, left: limitar(r.right - ancho, vw - ancho - MARGEN) });
    } else {
      // Encima (las pestañas de abajo en el celular).
      this.posicion.set({ top: Math.max(MARGEN, r.top - 12 - alto), left: limitar(r.left, vw - ancho - MARGEN) });
    }
  }

  protected tecla(e: KeyboardEvent): void {
    if (e.key === 'ArrowRight') this.tutorial.siguiente();
    else if (e.key === 'ArrowLeft') this.tutorial.anterior();
  }
}
