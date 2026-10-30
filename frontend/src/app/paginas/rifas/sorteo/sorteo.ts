import { DatePipe } from '@angular/common';
import { HttpClient, HttpParams } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { catchError, forkJoin, of } from 'rxjs';

import { Aviso } from '../../../compartido/aviso';
import { Dialogo } from '../../../compartido/dialogo';
import { mensajeError } from '../../../compartido/errores';
import { isoLocal } from '../../../compartido/fechas';
import { PESTANAS_RIFAS, Pestanas } from '../../../compartido/pestanas';
import { PesosPipe } from '../../../compartido/pesos.pipe';
import { AuthService } from '../../../core/auth/auth.service';
import { API } from '../../../core/modelos';
import { Alumno } from '../../alumnos/alumnos.modelos';
import { boleta } from '../boleta';
import { Acta, Rifa, Talonario } from '../rifas.modelos';

/** Lo mínimo que gira la pantalla antes de mostrar el ganador (el resultado ya lo eligió el servidor). */
const GIRO_MS = 2600;
const CAMBIO_MS = 70;

type FiltroTalonarios = 'todos' | 'sin_pagar' | 'pagados';

const rifaUrl = (id: string) => `${API}/rifas/${encodeURIComponent(id)}`;

/** Número de WhatsApp para wa.me: solo dígitos; los celulares colombianos de 10 dígitos llevan el 57. */
export function numeroWhatsApp(telefono: string | null): string | null {
  const digitos = (telefono ?? '').replace(/\D/g, '');
  if (digitos.length === 10 && digitos.startsWith('3')) return `57${digitos}`;
  return digitos.length >= 11 && digitos.length <= 15 ? digitos : null;
}

@Component({
  selector: 'app-sorteo',
  imports: [DatePipe, Aviso, Dialogo, PesosPipe, Pestanas],
  templateUrl: './sorteo.html',
  styleUrl: './sorteo.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SorteoPage implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private readonly ruta = inject(ActivatedRoute);
  private readonly router = inject(Router);

  protected readonly pestanas = PESTANAS_RIFAS;
  protected readonly puedeSortear = computed(() => this.auth.tiene('sorteo.jugar'));
  protected readonly hoy = isoLocal(new Date());
  protected readonly boleta = boleta;

  // ---------- Estado ----------
  protected readonly anio = new Date().getFullYear();
  protected readonly rifas = signal<Rifa[] | null>(null);
  protected readonly rifaId = signal<string | null>(null);
  protected readonly talonarios = signal<Talonario[] | null>(null);
  /** Jugadas de la rifa elegida, en orden. */
  protected readonly actas = signal<Acta[]>([]);
  protected readonly historial = signal<{ rifa: Rifa; acta: Acta }[]>([]);
  /** Dueño del talonario ganador (para avisarle por WhatsApp). */
  protected readonly ganador = signal<Alumno | null>(null);
  protected readonly filtro = signal<FiltroTalonarios>('todos');
  protected readonly confirmando = signal(false);
  protected readonly girando = signal(false);
  protected readonly recien = signal(false);
  /** Lo que muestra la pantalla grande mientras gira. */
  protected readonly destello = signal<{ codigo: string; boleta: number } | null>(null);
  protected readonly errorCarga = signal(false);
  protected readonly mensaje = signal<{ error: boolean; texto: string } | null>(null);

  private intervalo: ReturnType<typeof setInterval> | undefined;
  private espera: ReturnType<typeof setTimeout> | undefined;

  // ---------- Derivados ----------
  protected readonly vigentes = computed(() =>
    (this.rifas() ?? []).filter((r) => r.estado !== 'cancelada').sort((a, b) => a.numero - b.numero),
  );
  protected readonly rifa = computed(() => this.vigentes().find((r) => r.id === this.rifaId()) ?? null);
  /** La última jugada: es la que se muestra en la pantalla grande. */
  protected readonly acta = computed(() => this.actas().at(-1) ?? null);

  /** Boletas en la urna: las de los talonarios pagados al 100 %, menos las que ya ganaron en esta rifa. */
  protected readonly urna = computed(() => {
    const ganadas = new Set(this.actas().map((a) => boleta(a.codigo, a.boleta)));
    return (this.talonarios() ?? [])
      .filter((t) => t.pagado)
      .flatMap((t) => Array.from({ length: t.boletas }, (_, i) => ({ codigo: t.codigo, boleta: i + 1 })))
      .filter((b) => !ganadas.has(boleta(b.codigo, b.boleta)));
  });

  /** En la urna según el servidor (incluye talonarios que este usuario no ve). */
  protected readonly enUrna = computed(() => {
    const r = this.rifa();
    return r ? Math.max(0, r.talonarios_pagados * r.puestos_por_talonario - this.actas().length) : 0;
  });

  protected readonly sorteable = computed(() => {
    const r = this.rifa();
    return !!r && this.puedeSortear() && r.estado !== 'cancelada' && r.fecha_sorteo <= this.hoy && this.enUrna() > 0;
  });

  protected readonly listaTalonarios = computed(() => {
    const f = this.filtro();
    return [...(this.talonarios() ?? [])]
      .filter((t) => f === 'todos' || (f === 'pagados' ? t.pagado : !t.pagado))
      .sort((a, b) => a.codigo.localeCompare(b.codigo, 'es', { numeric: true }));
  });

  protected readonly conteo = computed(() => {
    const t = this.talonarios() ?? [];
    const pagados = t.filter((x) => x.pagado).length;
    return { todos: t.length, pagados, sin_pagar: t.length - pagados };
  });

  protected readonly porRama = computed(() =>
    (['femenina', 'masculina'] as const).map((rama) => {
      const lista = (this.talonarios() ?? []).filter((t) => t.rama === rama);
      const pagados = lista.filter((t) => t.pagado).length;
      return { rama, pagados, total: lista.length, pct: lista.length ? Math.round((pagados / lista.length) * 100) : 0 };
    }).filter((x) => x.total > 0),
  );

  /** wa.me al acudiente principal (o al alumno, si es mayor y tiene teléfono). */
  protected readonly enlaceWhatsApp = computed(() => {
    const a = this.acta();
    const r = this.rifa();
    const g = this.ganador();
    if (!a || !r || !g || g.id !== a.alumno_id) return null;
    const principal = g.acudientes.find((x) => x.principal) ?? g.acudientes[0];
    const numero = numeroWhatsApp(principal?.telefono ?? g.telefono);
    if (!numero) return null;
    const saludo = principal ? `¡Hola, ${principal.nombres}!` : `¡Hola, ${g.nombres}!`;
    const texto = `${saludo} Te escribimos del Club Deportivo Dragones: la boleta número ${this.dosDigitos(a.boleta)} `
      + `del talonario de ${g.nombres} ganó «${r.premio}» en la ${r.nombre}. ¡Felicitaciones! 🐉`;
    return `https://wa.me/${numero}?text=${encodeURIComponent(texto)}`;
  });

  constructor() {
    inject(DestroyRef).onDestroy(() => this.detenerGiro());
  }

  ngOnInit(): void {
    const params = new HttpParams().set('anio', this.anio);
    this.http.get<Rifa[]>(`${API}/rifas`, { params }).subscribe({
      next: (rifas) => {
        this.rifas.set(rifas);
        const pedida = this.ruta.snapshot.queryParamMap.get('rifa');
        const elegida = this.vigentes().find((r) => r.id === pedida) ?? this.porDefecto();
        if (elegida) this.elegir(elegida);
        this.cargarHistorial();
      },
      error: () => this.errorCarga.set(true),
    });
  }

  /** La que toca jugar (abierta y ya en fecha), si no la próxima abierta, si no la última sorteada. */
  private porDefecto(): Rifa | undefined {
    const v = this.vigentes();
    const abiertas = v.filter((r) => r.estado === 'abierta');
    return abiertas.find((r) => r.fecha_sorteo <= this.hoy) ?? abiertas[0] ?? v.filter((r) => r.estado === 'sorteada').at(-1);
  }

  protected elegir(r: Rifa): void {
    if (this.girando()) return;
    this.rifaId.set(r.id);
    this.talonarios.set(null);
    this.actas.set([]);
    this.ganador.set(null);
    this.recien.set(false);
    void this.router.navigate([], { queryParams: { rifa: r.id }, replaceUrl: true });
    forkJoin({
      talonarios: this.http.get<Talonario[]>(`${rifaUrl(r.id)}/talonarios`),
      actas: r.estado === 'sorteada' ? this.http.get<Acta[]>(`${rifaUrl(r.id)}/actas`) : of([]),
    }).subscribe({
      next: (x) => {
        if (this.rifaId() !== r.id) return;
        this.talonarios.set(x.talonarios);
        this.actas.set(x.actas);
        this.cargarGanador();
      },
      error: () => this.errorCarga.set(true),
    });
  }

  /** Datos de contacto del dueño del talonario ganador (si quien mira no puede verlos, no hay botón). */
  private cargarGanador(): void {
    const a = this.acta();
    if (!a) return this.ganador.set(null);
    this.http.get<Alumno>(`${API}/alumnos/${encodeURIComponent(a.alumno_id)}`)
      .pipe(catchError(() => of(null)))
      .subscribe((g) => this.ganador.set(g));
  }

  private cargarHistorial(): void {
    const sorteadas = this.vigentes().filter((r) => r.estado === 'sorteada');
    if (!sorteadas.length) return this.historial.set([]);
    forkJoin(sorteadas.map((r) => this.http.get<Acta[]>(`${rifaUrl(r.id)}/actas`))).subscribe({
      next: (porRifa) => this.historial.set(
        sorteadas.flatMap((rifa, i) => (porRifa[i] ?? []).map((acta) => ({ rifa, acta })))
          .sort((x, y) => y.acta.jugado_en.localeCompare(x.acta.jugado_en)),
      ),
      error: () => this.historial.set([]),
    });
  }

  // ---------- Sorteo ----------
  protected jugar(): void {
    const r = this.rifa();
    if (!r || this.girando()) return;
    this.confirmando.set(false);
    this.mensaje.set(null);
    this.girando.set(true);
    this.recien.set(false);
    const sinMovimiento = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
    const urna = this.urna();
    if (!sinMovimiento && urna.length) {
      this.intervalo = setInterval(() => this.destello.set(urna[Math.floor(Math.random() * urna.length)] ?? null), CAMBIO_MS);
    }
    const inicio = Date.now();
    this.http.post<Acta>(`${rifaUrl(r.id)}/sorteo`, {}).subscribe({
      next: (acta) => {
        const resta = sinMovimiento ? 0 : Math.max(0, GIRO_MS - (Date.now() - inicio));
        this.espera = setTimeout(() => {
          this.detenerGiro();
          this.actas.update((lista) => [...lista, acta]);
          this.recien.set(true);
          this.cargarGanador();
          this.refrescarRifa(r.id);
        }, resta);
      },
      error: (e) => {
        this.detenerGiro();
        this.mensaje.set({ error: true, texto: mensajeError(e) });
      },
    });
  }

  private detenerGiro(): void {
    clearInterval(this.intervalo);
    clearTimeout(this.espera);
    this.girando.set(false);
    this.destello.set(null);
  }

  private refrescarRifa(id: string): void {
    this.http.get<Rifa>(rifaUrl(id)).subscribe((r) => {
      this.rifas.update((lista) => lista?.map((x) => (x.id === r.id ? r : x)) ?? lista);
      this.cargarHistorial();
    });
  }

  protected huellaCorta(h: string): string {
    return `${h.slice(0, 10)}…${h.slice(-6)}`;
  }

  protected dosDigitos(n: number): string {
    return String(n).padStart(2, '0');
  }
}
