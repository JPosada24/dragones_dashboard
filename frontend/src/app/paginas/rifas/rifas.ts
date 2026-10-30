import { DatePipe } from '@angular/common';
import { HttpClient, HttpParams } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Observable, forkJoin } from 'rxjs';

import { Aviso } from '../../compartido/aviso';
import { Dialogo } from '../../compartido/dialogo';
import { PESTANAS_RIFAS, Pestanas } from '../../compartido/pestanas';
import { mensajeError } from '../../compartido/errores';
import { diasEntre, isoLocal } from '../../compartido/fechas';
import { PesosPipe } from '../../compartido/pesos.pipe';
import { AuthService } from '../../core/auth/auth.service';
import { API } from '../../core/modelos';
import { boleta } from './boleta';
import { FilaPazYSalvo, PagoTalonario, Rifa, Talonario } from './rifas.modelos';

const rifaUrl = (id: string) => `${API}/rifas/${encodeURIComponent(id)}`;

@Component({
  selector: 'app-rifas',
  imports: [DatePipe, ReactiveFormsModule, RouterLink, Aviso, Dialogo, PesosPipe, Pestanas],
  templateUrl: './rifas.html',
  styleUrl: './rifas.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RifasPage implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly pesos = new PesosPipe();
  protected readonly pestanas = PESTANAS_RIFAS;

  // ---------- Permisos (la autorización real la hace el servidor) ----------
  protected readonly esStaff = computed(() => this.auth.tieneAlguno(['alumnos.ver_todos', 'alumnos.ver_rama']));
  protected readonly veTodasLasRamas = computed(() => this.auth.tiene('alumnos.ver_todos'));
  protected readonly puedeGestionar = computed(() => this.auth.tiene('rifas.gestionar'));
  protected readonly puedeCobrar = computed(() => this.auth.tiene('pagos.registrar'));
  protected readonly puedeAnular = computed(() => this.auth.tiene('pagos.anular'));
  protected readonly puedeSortear = computed(() => this.auth.tiene('sorteo.jugar'));

  protected readonly hoy = isoLocal(new Date());

  // ---------- Estado ----------
  protected readonly anio = signal(new Date().getFullYear());
  protected readonly rifas = signal<Rifa[] | null>(null);
  /** Talonarios de cada rifa del año (por id de rifa). */
  protected readonly talonarios = signal<Record<string, Talonario[]>>({});
  protected readonly filtroRama = signal<'' | 'femenina' | 'masculina'>('');
  protected readonly soloConDeuda = signal(false);
  protected readonly errorCarga = signal(false);
  protected readonly mensaje = signal<{ error: boolean; texto: string } | null>(null);
  protected readonly errorDialogo = signal<string | null>(null);
  protected readonly ocupado = signal(false);

  // ---------- Ventanas emergentes ----------
  protected readonly creando = signal(false);
  protected readonly cancelando = signal<Rifa | null>(null);
  /** Talonario abierto (con su rifa). */
  protected readonly abierto = signal<{ rifa: Rifa; talonarioId: string } | null>(null);
  protected readonly pagandoTalonario = signal(false);
  protected readonly anulandoPago = signal<PagoTalonario | null>(null);
  protected readonly eliminando = signal<Rifa | null>(null);

  protected readonly formRifa = this.fb.group({
    nombre: ['', [Validators.required, Validators.minLength(3), Validators.maxLength(120)]],
    premio: ['', [Validators.required, Validators.minLength(3), Validators.maxLength(255)]],
    fecha_sorteo: ['', Validators.required],
  });
  protected readonly formCancelar = this.fb.group({ motivo: ['', Validators.maxLength(255)] });
  protected readonly formPago = this.fb.group({
    monto: [0, [Validators.required, Validators.min(1), Validators.max(10_000_000)]],
    fecha: [this.hoy, Validators.required],
  });
  protected readonly formAnular = this.fb.group({ motivo: ['', Validators.maxLength(255)] });

  // ---------- Derivados ----------
  /** Rifas que cuentan para el paz y salvo (las canceladas no). */
  protected readonly vigentes = computed(() =>
    (this.rifas() ?? []).filter((r) => r.estado !== 'cancelada').sort((a, b) => a.numero - b.numero),
  );

  protected readonly indicadores = computed(() => {
    const v = this.vigentes();
    const talonarios = v.reduce((t, r) => t + r.talonarios, 0);
    return {
      rifas: v.length,
      recaudado: v.reduce((t, r) => t + r.recaudado, 0),
      porRecaudar: v.filter((r) => r.estado === 'abierta').reduce((t, r) => t + (r.esperado - r.recaudado), 0),
      pagados: v.reduce((t, r) => t + r.talonarios_pagados, 0),
      talonarios,
    };
  });

  /** Matriz alumno × rifa del año. */
  protected readonly filas = computed<FilaPazYSalvo[]>(() => {
    const rifas = this.vigentes();
    const porRifa = this.talonarios();
    const filas = new Map<string, FilaPazYSalvo>();
    rifas.forEach((r, i) => {
      for (const t of porRifa[r.id] ?? []) {
        const f = filas.get(t.alumno_id) ?? {
          alumno_id: t.alumno_id, codigo: t.codigo, alumno_nombre: t.alumno_nombre, rama: t.rama,
          celdas: rifas.map(() => null), deuda: 0,
        };
        f.celdas[i] = t;
        f.deuda += t.saldo;
        filas.set(t.alumno_id, f);
      }
    });
    const rama = this.filtroRama();
    return [...filas.values()]
      .filter((f) => (!rama || f.rama === rama) && (!this.soloConDeuda() || f.deuda > 0))
      .sort((a, b) => a.alumno_nombre.localeCompare(b.alumno_nombre));
  });

  /** El talonario abierto, siempre al día con lo que devuelve la API. */
  protected readonly talonario = computed(() => {
    const a = this.abierto();
    return a ? ((this.talonarios()[a.rifa.id] ?? []).find((t) => t.id === a.talonarioId) ?? null) : null;
  });

  ngOnInit(): void {
    this.cargar();
  }

  protected cargar(): void {
    const params = new HttpParams().set('anio', this.anio());
    this.http.get<Rifa[]>(`${API}/rifas`, { params }).subscribe({
      next: (rifas) => {
        this.errorCarga.set(false);
        this.rifas.set(rifas);
        this.cargarTalonarios(rifas.filter((r) => r.estado !== 'cancelada'));
      },
      error: () => this.errorCarga.set(true),
    });
  }

  private cargarTalonarios(rifas: Rifa[]): void {
    if (!rifas.length) return this.talonarios.set({});
    const pedidos = Object.fromEntries(rifas.map((r) => [r.id, this.http.get<Talonario[]>(`${rifaUrl(r.id)}/talonarios`)]));
    forkJoin(pedidos as Record<string, Observable<Talonario[]>>).subscribe({
      next: (r) => this.talonarios.set(r),
      error: () => this.errorCarga.set(true),
    });
  }

  protected cambiarAnio(delta: number): void {
    this.anio.update((a) => a + delta);
    this.rifas.set(null);
    this.talonarios.set({});
    this.cargar();
  }

  // ---------- Presentación ----------
  protected pct(parte: number, total: number): string {
    return total ? `${Math.round((parte / total) * 100)}%` : '0%';
  }

  protected cuando(iso: string): string {
    const d = diasEntre(this.hoy, iso);
    if (d === 0) return 'hoy';
    return d > 0 ? `en ${d} d` : `hace ${-d} d`;
  }

  protected readonly boleta = boleta;


  protected sorteable(r: Rifa): boolean {
    return this.puedeSortear() && r.estado === 'abierta' && r.fecha_sorteo <= this.hoy; // las sorteadas: «Ver sorteos»
  }

  /** Un pago positivo que todavía no fue revertido por una anulación. */
  protected anulable(t: Talonario, pago: PagoTalonario): boolean {
    return this.puedeAnular() && pago.monto > 0 && !this.anulado(t, pago);
  }

  protected anulado(t: Talonario, pago: PagoTalonario): boolean {
    return t.pagos.some((x) => x.anula_id === pago.id);
  }

  /** Reemplaza un talonario (respuesta de la API) y refresca los totales de su rifa. */
  private actualizarTalonario(rifa: Rifa, t: Talonario): void {
    this.talonarios.update((todo) => ({
      ...todo, [rifa.id]: (todo[rifa.id] ?? []).map((x) => (x.id === t.id ? t : x)),
    }));
    this.refrescarRifa(rifa.id);
  }

  private refrescarRifa(id: string): void {
    this.http.get<Rifa>(rifaUrl(id)).subscribe((r) => {
      this.rifas.update((lista) => lista?.map((x) => (x.id === r.id ? r : x)) ?? lista);
      const a = this.abierto();
      if (a?.rifa.id === r.id) this.abierto.set({ ...a, rifa: r });
    });
  }

  // ---------- Crear y cancelar ----------
  protected abrirNueva(): void {
    const n = (this.rifas() ?? []).filter((r) => r.estado !== 'cancelada').length + 1;
    this.formRifa.reset({ nombre: `Rifa ${n} de ${this.anio()}`, premio: '', fecha_sorteo: '' });
    this.abrir(() => this.creando.set(true));
  }

  protected guardarRifa(): void {
    if (this.formRifa.invalid) return this.errorDialogo.set('Completa el nombre, el premio y la fecha del sorteo.');
    const cuerpo = { ...this.formRifa.getRawValue(), anio: this.anio() };
    this.ejecutar(this.http.post<Rifa>(`${API}/rifas`, cuerpo), (r) => {
      this.creando.set(false);
      this.cargar();
      this.avisar(`«${r.nombre}» creada con ${r.talonarios} talonarios (uno por alumno inscrito).`);
    });
  }

  protected abrirCancelar(r: Rifa): void {
    this.formCancelar.reset({ motivo: '' });
    this.abrir(() => this.cancelando.set(r));
  }

  protected guardarCancelacion(): void {
    const r = this.cancelando();
    if (!r) return;
    const motivo = this.formCancelar.getRawValue().motivo.trim() || null;
    this.ejecutar(this.http.post<Rifa>(`${rifaUrl(r.id)}/cancelar`, { motivo }), () => {
      this.cancelando.set(null);
      this.cargar();
      this.avisar(`«${r.nombre}» cancelada: ya no cuenta para el paz y salvo.`);
    });
  }

  protected abrirEliminar(r: Rifa): void {
    this.abrir(() => this.eliminando.set(r));
  }

  protected eliminar(): void {
    const r = this.eliminando();
    if (!r) return;
    this.ejecutar(this.http.delete(rifaUrl(r.id)), () => {
      this.eliminando.set(null);
      this.cargar();
      this.avisar(`«${r.nombre}» eliminada.`);
    });
  }

  /** Da talonario a quienes se inscribieron después de crear la rifa. */
  protected asignar(r: Rifa): void {
    this.mensaje.set(null);
    this.ocupado.set(true);
    this.http.post<{ asignados: number }>(`${rifaUrl(r.id)}/talonarios`, {}).subscribe({
      next: ({ asignados }) => {
        this.ocupado.set(false);
        if (asignados) this.cargar();
        this.avisar(asignados
          ? `${asignados} ${asignados === 1 ? 'talonario asignado' : 'talonarios asignados'} en «${r.nombre}».`
          : 'Todos los alumnos inscritos ya tienen talonario en esta rifa.');
      },
      error: (e) => {
        this.ocupado.set(false);
        this.mensaje.set({ error: true, texto: mensajeError(e) });
      },
    });
  }

  // ---------- Talonario ----------
  protected abrirTalonario(rifa: Rifa, t: Talonario): void {
    this.abrir(() => this.abierto.set({ rifa, talonarioId: t.id }));
  }

  protected abrirPagoTalonario(t: Talonario): void {
    this.formPago.reset({ monto: t.saldo, fecha: this.hoy });
    this.errorDialogo.set(null);
    this.pagandoTalonario.set(true);
  }

  protected guardarPagoTalonario(): void {
    const a = this.abierto();
    const t = this.talonario();
    if (!a || !t) return;
    if (this.formPago.invalid) return this.errorDialogo.set('Revisa el valor y la fecha del pago.');
    const url = `${rifaUrl(a.rifa.id)}/talonarios/${encodeURIComponent(t.id)}/pagos`;
    this.ejecutar(this.http.post<Talonario>(url, this.formPago.getRawValue()), (r) => {
      this.pagandoTalonario.set(false);
      this.actualizarTalonario(a.rifa, r);
      this.avisar(r.pagado
        ? `Talonario de ${r.alumno_nombre} pagado: queda a paz y salvo en «${a.rifa.nombre}».`
        : `Pago registrado. Saldo del talonario: ${this.pesos.transform(r.saldo)}.`);
    });
  }

  protected abrirAnularPago(pago: PagoTalonario): void {
    this.formAnular.reset({ motivo: '' });
    this.errorDialogo.set(null);
    this.anulandoPago.set(pago);
  }

  protected guardarAnulacion(): void {
    const a = this.abierto();
    const pago = this.anulandoPago();
    if (!a || !pago) return;
    const motivo = this.formAnular.getRawValue().motivo.trim() || null;
    const url = `${rifaUrl(a.rifa.id)}/talonarios/${encodeURIComponent(a.talonarioId)}/pagos/${encodeURIComponent(pago.id)}/anular`;
    this.ejecutar(this.http.post<Talonario>(url, { motivo }), (r) => {
      this.anulandoPago.set(null);
      this.actualizarTalonario(a.rifa, r);
      this.avisar('Pago anulado: queda en el historial como un movimiento en negativo.');
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
