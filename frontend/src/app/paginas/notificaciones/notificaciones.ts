import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';

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

@Component({
  selector: 'app-notificaciones',
  imports: [DatePipe],
  templateUrl: './notificaciones.html',
  styleUrl: './notificaciones.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class NotificacionesPage implements OnInit {
  private readonly servicio = inject(NotificacionesService);

  protected readonly avisos = signal<Notificacion[] | null>(null);
  protected readonly error = signal(false);

  ngOnInit(): void {
    this.cargar();
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

  protected hayNoLeidas(): boolean {
    return this.avisos()?.some((a) => !a.leida) ?? false;
  }

  private cargar(): void {
    this.servicio.listar().subscribe({
      next: (l) => this.avisos.set(l),
      error: () => this.error.set(true),
    });
  }
}
