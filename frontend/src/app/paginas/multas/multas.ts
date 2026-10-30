import { DatePipe } from '@angular/common';
import { HttpClient, HttpParams } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Observable } from 'rxjs';

import { Aviso } from '../../compartido/aviso';
import { Dialogo } from '../../compartido/dialogo';
import { mensajeError } from '../../compartido/errores';
import { diasEntre, isoLocal } from '../../compartido/fechas';
import { PesosPipe } from '../../compartido/pesos.pipe';
import { AuthService } from '../../core/auth/auth.service';
import { API } from '../../core/modelos';
import { EstadoMulta, GrupoMultas, Multa, SituacionMora } from './multas.modelos';

const LIMITE = 500;
const multaUrl = (id: string) => `${API}/multas/${encodeURIComponent(id)}`;

@Component({
  selector: 'app-multas',
  imports: [DatePipe, ReactiveFormsModule, RouterLink, Aviso, Dialogo, PesosPipe],
  templateUrl: './multas.html',
  styleUrl: './multas.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MultasPage implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly pesos = new PesosPipe();

  // ---------- Permisos (la autorización real la hace el servidor) ----------
  protected readonly esStaff = computed(() => this.auth.tieneAlguno(['alumnos.ver_todos', 'alumnos.ver_rama']));
  protected readonly veTodasLasRamas = computed(() => this.auth.tiene('alumnos.ver_todos'));
  protected readonly puedeCobrar = computed(() => this.auth.tiene('pagos.registrar'));
  protected readonly puedeAnular = computed(() => this.auth.tiene('multas.anular'));

  protected readonly hoy = isoLocal(new Date());
  protected readonly limite = LIMITE;

  // ---------- Estado ----------
  protected readonly estado = signal<EstadoMulta>('pendiente');
  protected readonly filtroRama = signal<'' | 'femenina' | 'masculina'>('');
  protected readonly multas = signal<Multa[] | null>(null);
  protected readonly mora = signal<SituacionMora[] | null>(null);
  protected readonly errorCarga = signal(false);
  protected readonly mensaje = signal<{ error: boolean; texto: string } | null>(null);
  protected readonly errorDialogo = signal<string | null>(null);
  protected readonly ocupado = signal(false);

  /** Multas que se van a cobrar juntas (las de un alumno, o una sola). */
  protected readonly cobrando = signal<Multa[] | null>(null);
  protected readonly anulando = signal<Multa | null>(null);

  protected readonly formCobro = this.fb.group({ fecha_pago: [this.hoy, Validators.required] });
  protected readonly formAnular = this.fb.group({
    motivo: ['', [Validators.required, Validators.minLength(10), Validators.maxLength(255)]],
  });

  // ---------- Derivados ----------
  protected readonly visibles = computed(() => {
    const r = this.filtroRama();
    return (this.multas() ?? []).filter((m) => !r || m.rama === r);
  });

  /** Pendientes agrupadas por alumno: quien más debe, primero. */
  protected readonly grupos = computed<GrupoMultas[]>(() => {
    const porAlumno = new Map<string, GrupoMultas>();
    for (const m of this.visibles()) {
      const g = porAlumno.get(m.alumno_id)
        ?? { alumno_id: m.alumno_id, alumno_nombre: m.alumno_nombre, rama: m.rama, multas: [], total: 0 };
      g.multas.push(m);
      g.total += m.valor;
      porAlumno.set(m.alumno_id, g);
    }
    return [...porAlumno.values()].sort((a, b) => b.total - a.total || a.alumno_nombre.localeCompare(b.alumno_nombre));
  });

  protected readonly moraVisible = computed(() => {
    const r = this.filtroRama();
    return (this.mora() ?? [])
      .filter((s) => !r || s.rama === r)
      .sort((a, b) => Number(b.en_mora) - Number(a.en_mora) || a.entra_en_mora.localeCompare(b.entra_en_mora));
  });

  protected readonly indicadores = computed(() => {
    const pendientes = this.estado() === 'pendiente' ? this.visibles() : [];
    const mora = this.moraVisible();
    return {
      pendientes: pendientes.length,
      porCobrar: pendientes.reduce((t, m) => t + m.valor, 0),
      alumnos: new Set(pendientes.map((m) => m.alumno_id)).size,
      riesgo: mora.filter((s) => !s.en_mora).length,
      enMora: mora.filter((s) => s.en_mora).length,
    };
  });

  protected readonly totalCobro = computed(() => (this.cobrando() ?? []).reduce((t, m) => t + m.valor, 0));

  ngOnInit(): void {
    this.cargarMultas();
    if (this.esStaff()) this.cargarMora();
  }

  protected cargarMultas(): void {
    this.multas.set(null);
    const params = new HttpParams().set('estado', this.estado()).set('limit', LIMITE);
    this.http.get<Multa[]>(`${API}/multas`, { params }).subscribe({
      next: (lista) => {
        this.errorCarga.set(false);
        this.multas.set(lista);
      },
      error: () => this.errorCarga.set(true),
    });
  }

  private cargarMora(): void {
    this.http.get<SituacionMora[]>(`${API}/mora`).subscribe({
      next: (lista) => this.mora.set(lista),
      error: () => this.mora.set([]),
    });
  }

  protected cambiarEstado(e: EstadoMulta): void {
    if (this.estado() === e) return;
    this.estado.set(e);
    this.cargarMultas();
  }

  /** "en 12 d", "hoy" o "hace 3 d" respecto a hoy. */
  protected cuando(iso: string): string {
    const d = diasEntre(this.hoy, iso);
    if (d === 0) return 'hoy';
    return d > 0 ? `en ${d} d` : `hace ${-d} d`;
  }

  // ---------- Cobro ----------
  protected abrirCobro(multas: Multa[]): void {
    this.formCobro.reset({ fecha_pago: this.hoy });
    this.abrir(() => this.cobrando.set(multas));
  }

  /** No antes del entrenamiento más reciente de las multas que se cobran. */
  protected minimoPago(multas: Multa[]): string {
    return multas.reduce((max, m) => (m.fecha_sesion > max ? m.fecha_sesion : max), '');
  }

  protected guardarCobro(): void {
    const multas = this.cobrando();
    if (!multas?.length) return;
    if (this.formCobro.invalid) return this.errorDialogo.set('Indica la fecha del pago.');
    const cuerpo = { multa_ids: multas.map((m) => m.id), fecha_pago: this.formCobro.getRawValue().fecha_pago };
    this.ejecutar(this.http.post<Multa[]>(`${API}/multas/pagos`, cuerpo), (pagadas) => {
      this.cobrando.set(null);
      const ids = new Set(pagadas.map((m) => m.id));
      this.multas.update((lista) => lista?.filter((m) => !ids.has(m.id)) ?? lista);
      const total = pagadas.reduce((t, m) => t + m.valor, 0);
      const quien = multas[0]?.alumno_nombre ?? '';
      const n = pagadas.length;
      this.avisar(`${n === 1 ? 'Multa cobrada' : `${n} multas cobradas`} a ${quien}: ${this.pesos.transform(total)}.`);
      this.cargarMora(); // pagar puede sacar al alumno de la mora
    });
  }

  // ---------- Anulación ----------
  protected abrirAnular(m: Multa): void {
    this.formAnular.reset({ motivo: '' });
    this.abrir(() => this.anulando.set(m));
  }

  protected guardarAnulacion(): void {
    const m = this.anulando();
    if (!m) return;
    if (this.formAnular.invalid) return this.errorDialogo.set('Explica el motivo (al menos 10 caracteres).');
    this.ejecutar(this.http.post<Multa>(`${multaUrl(m.id)}/anular`, this.formAnular.getRawValue()), () => {
      this.anulando.set(null);
      this.multas.update((lista) => lista?.filter((x) => x.id !== m.id) ?? lista);
      this.avisar(`Multa de ${m.alumno_nombre} anulada.`);
      this.cargarMora();
    });
  }

  // ---------- Utilidades ----------
  private abrir(mostrar: () => void): void {
    this.errorDialogo.set(null);
    this.mensaje.set(null);
    mostrar();
  }

  /** Las acciones van en popups: el error se muestra dentro, sin perder lo escrito. */
  private ejecutar<T>(peticion: Observable<T>, ok: (r: T) => void): void {
    this.ocupado.set(true);
    this.errorDialogo.set(null);
    peticion.subscribe({
      next: (r) => {
        this.ocupado.set(false);
        ok(r);
      },
      error: (e) => {
        this.ocupado.set(false);
        this.errorDialogo.set(mensajeError(e));
      },
    });
  }

  private avisar(texto: string): void {
    this.mensaje.set({ error: false, texto });
  }
}
