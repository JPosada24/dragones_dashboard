import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { Aviso } from '../../compartido/aviso';
import { Operacion } from '../../compartido/operacion';
import { PesosPipe } from '../../compartido/pesos.pipe';
import { AuthService } from '../../core/auth/auth.service';
import { IngresoMes, Ingresos, ReportesApi } from './reportes.api';

const MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio', 'Julio', 'Agosto', 'Septiembre', 'Octubre',
  'Noviembre', 'Diciembre'];

/** Ingresos del club por mes y concepto, y descarga de los movimientos para la contabilidad. */
@Component({
  selector: 'app-reportes',
  imports: [ReactiveFormsModule, Aviso, PesosPipe],
  templateUrl: './reportes.html',
  styleUrl: './reportes.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ReportesPage implements OnInit {
  private readonly api = inject(ReportesApi);
  private readonly auth = inject(AuthService);
  private readonly fb = inject(FormBuilder).nonNullable;

  protected readonly op = new Operacion();
  protected readonly meses = MESES;
  protected readonly puedeExportar = computed(() => this.auth.tiene('reportes.exportar'));
  protected readonly anio = signal(new Date().getFullYear());
  protected readonly datos = signal<Ingresos | null>(null);
  protected readonly error = signal(false);

  /** El mes con más ingresos fija el 100 % de las barras. */
  private readonly maximo = computed(() => Math.max(1, ...(this.datos()?.meses ?? []).map((m) => m.total)));
  protected readonly indicadores = computed(() => {
    const d = this.datos();
    if (!d) return null;
    const conIngresos = d.meses.filter((m) => m.total > 0);
    const mejor = [...d.meses].sort((a, b) => b.total - a.total)[0];
    const suma = (c: keyof Omit<IngresoMes, 'mes' | 'total'>) => d.meses.reduce((t, m) => t + m[c], 0);
    return {
      total: d.total,
      promedio: conIngresos.length ? Math.round(d.total / conIngresos.length) : 0,
      mejor: mejor && mejor.total > 0 ? MESES[mejor.mes - 1] : '—',
      inscripciones: suma('inscripciones'),
      otros: suma('multas') + suma('rifas') + suma('torneos'),
    };
  });

  protected readonly form = this.fb.group({
    desde: ['', Validators.required],
    hasta: ['', Validators.required],
  });

  ngOnInit(): void {
    this.cargar();
  }

  protected cambiarAnio(paso: number): void {
    this.anio.update((a) => a + paso);
    this.cargar();
  }

  private cargar(): void {
    this.datos.set(null);
    this.error.set(false);
    this.api.ingresos(this.anio()).subscribe({
      next: (d) => this.datos.set(d),
      error: () => this.error.set(true),
    });
  }

  protected ancho(m: IngresoMes): string {
    return `${Math.max(0, Math.round((m.total / this.maximo()) * 100))}%`;
  }

  protected descargar(): void {
    const { desde, hasta } = this.form.getRawValue();
    if (this.form.invalid || hasta < desde) {
      this.op.mensaje.set({ error: true, texto: 'Elige un rango válido (la fecha final después de la inicial).' });
      return;
    }
    this.op.ejecutar(this.api.movimientos(desde, hasta), (blob) => {
      const enlace = document.createElement('a');
      enlace.href = URL.createObjectURL(blob);
      enlace.download = `movimientos-${desde}-a-${hasta}.csv`;
      enlace.click();
      setTimeout(() => URL.revokeObjectURL(enlace.href), 1000);
      this.op.exito('Movimientos descargados.');
    }, { enDialogo: false });
  }
}
