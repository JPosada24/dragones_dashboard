import { DatePipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { forkJoin, map, of, switchMap } from 'rxjs';

import { isoLocal, sumarDias } from '../../compartido/fechas';
import { ESTADO_INSCRIPCION } from '../../compartido/estados';
import { PesosPipe } from '../../compartido/pesos.pipe';
import { AuthService } from '../../core/auth/auth.service';
import { API } from '../../core/modelos';
import { AlumnoBasico, EstadoCuenta, ResumenStaff, SesionBasica } from './resumen.modelos';

@Component({
  selector: 'app-resumen',
  imports: [RouterLink, DatePipe, PesosPipe],
  templateUrl: './resumen.html',
  styleUrl: './resumen.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ResumenPage implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);

  /** Staff (todo el club o su rama) ve el tablero; las familias ven a sus hijos. */
  protected readonly esStaff = computed(() => this.auth.tiene('alumnos.ver_todos'));
  protected readonly error = signal(false);

  protected readonly resumen = signal<ResumenStaff | null>(null);
  protected readonly familia = signal<{ alumno: AlumnoBasico; cuenta: EstadoCuenta }[] | null>(null);
  protected readonly proximas = signal<SesionBasica[]>([]);

  protected readonly estadoInscripcion = ESTADO_INSCRIPCION;

  ngOnInit(): void {
    if (this.esStaff()) {
      this.http.get<ResumenStaff>(`${API}/resumen`).subscribe({
        next: (r) => this.resumen.set(r),
        error: () => this.error.set(true),
      });
    } else {
      this.cargarFamilia();
    }
  }

  /** Porcentaje como texto para anchos de barras. */
  protected pct(parte: number, total: number): string {
    return total > 0 ? `${Math.round((parte / total) * 100)}%` : '0%';
  }

  private cargarFamilia(): void {
    const hoy = new Date();
    const enUnaSemana = sumarDias(hoy, 7);
    this.http
      .get<AlumnoBasico[]>(`${API}/alumnos`)
      .pipe(
        switchMap((alumnos) =>
          alumnos.length === 0
            ? of([])
            : forkJoin(
                alumnos.map((a) =>
                  this.http
                    .get<EstadoCuenta>(`${API}/alumnos/${encodeURIComponent(a.id)}/estado-cuenta`)
                    .pipe(map((cuenta) => ({ alumno: a, cuenta }))),
                ),
              ),
        ),
      )
      .subscribe({ next: (f) => this.familia.set(f), error: () => this.error.set(true) });
    this.http
      .get<SesionBasica[]>(`${API}/sesiones`, { params: { desde: isoLocal(hoy), hasta: isoLocal(enUnaSemana) } })
      .subscribe({ next: (s) => this.proximas.set(s.filter((x) => !x.cancelada).slice(0, 6)), error: () => undefined });
  }
}
