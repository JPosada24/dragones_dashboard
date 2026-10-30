import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, ElementRef, HostListener, inject, signal } from '@angular/core';

import { Notificacion } from '../../core/modelos';
import { NotificacionesService } from '../../core/notificaciones.service';

const ICONOS: Record<string, string> = {
  multa: 'gavel',
  recordatorio_inscripcion: 'schedule',
  inscripcion_vencida: 'event_busy',
  justificacion: 'task_alt',
  alerta_inasistencia: 'warning',
  aviso_mora: 'hourglass_top',
  mora: 'report',
  mora_staff: 'report',
  fin_mora: 'verified',
};

let siguienteId = 0;

/** Campana de avisos: muestra el conteo de no leídos y despliega la bandeja sin salir de la pantalla. */
@Component({
  selector: 'app-campana',
  imports: [DatePipe],
  templateUrl: './campana.html',
  styleUrl: './campana.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Campana {
  private readonly servicio = inject(NotificacionesService);
  private readonly host = inject<ElementRef<HTMLElement>>(ElementRef);

  protected readonly noLeidas = this.servicio.noLeidas;
  protected readonly abierta = signal(false);
  protected readonly avisos = signal<Notificacion[] | null>(null);
  protected readonly error = signal(false);
  protected readonly idPanel = `panel-avisos-${siguienteId++}`;

  protected alternar(): void {
    if (this.abierta()) {
      this.abierta.set(false);
      return;
    }
    this.abierta.set(true);
    this.error.set(false);
    this.servicio.listar().subscribe({
      next: (l) => {
        this.avisos.set(l);
        this.noLeidas.set(l.filter((a) => !a.leida).length);
      },
      error: () => this.error.set(true),
    });
  }

  protected icono(tipo: string): string {
    return ICONOS[tipo] ?? 'notifications';
  }

  protected leer(a: Notificacion): void {
    if (a.leida) return;
    this.servicio.marcarLeida(a.id).subscribe(() =>
      this.avisos.update((l) => l?.map((x) => (x.id === a.id ? { ...x, leida: true } : x)) ?? null),
    );
  }

  protected leerTodas(): void {
    this.servicio.marcarTodas().subscribe(() => this.avisos.update((l) => l?.map((x) => ({ ...x, leida: true })) ?? null));
  }

  /** Se cierra al hacer clic fuera o con Escape. */
  @HostListener('document:click', ['$event'])
  protected clicFuera(e: MouseEvent): void {
    if (this.abierta() && !this.host.nativeElement.contains(e.target as Node)) this.abierta.set(false);
  }

  @HostListener('document:keydown.escape')
  protected escape(): void {
    if (!this.abierta()) return;
    this.abierta.set(false);
    this.host.nativeElement.querySelector<HTMLButtonElement>('.disparador')?.focus();
  }
}
