import { DatePipe } from '@angular/common';
import { HttpClient, HttpParams } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Observable } from 'rxjs';

import { Aviso } from '../../compartido/aviso';
import { Dialogo } from '../../compartido/dialogo';
import { mensajeError } from '../../compartido/errores';
import { ESTADO_INSCRIPCION } from '../../compartido/estados';
import { desdeIso, diasEntre, formatoFecha, isoLocal, sumarDias } from '../../compartido/fechas';
import { PesosPipe } from '../../compartido/pesos.pipe';
import { AuthService } from '../../core/auth/auth.service';
import { API } from '../../core/modelos';
import { Alumno } from '../alumnos/alumnos.modelos';
import { PestanasAlumnos } from '../alumnos/pestanas-alumnos';
import { FormaPago, inscribirConPago, inscripcionUrl, problemaPago, resumenPago } from './inscribir';
import { EstadoInscripcion, Inscripcion, PagoInscripcion } from './inscripciones.modelos';

/** Días antes del límite en que una inscripción "vence pronto" (igual que el Resumen). */
const DIAS_VENCE_PRONTO = 7;
/** El año se pide completo; el club es pequeño. Si se alcanza, se avisa. */
const LIMITE = 200;

type Filtro = 'pendientes' | 'pronto' | 'activas' | 'revision' | 'cerradas' | 'todas';

const FILTROS: { valor: Filtro; texto: string; estados: EstadoInscripcion[] | null }[] = [
  { valor: 'pendientes', texto: 'Pendientes de pago', estados: ['pendiente_pago'] },
  { valor: 'pronto', texto: 'Vencen pronto', estados: ['pendiente_pago'] },
  { valor: 'activas', texto: 'Activas', estados: ['activo'] },
  { valor: 'revision', texto: 'En revisión', estados: ['a_expulsar'] },
  { valor: 'cerradas', texto: 'Rechazadas y expulsadas', estados: ['rechazado', 'expulsado'] },
  { valor: 'todas', texto: 'Todas', estados: null },
];

/** Cambios de estado posibles a mano (los demás ocurren solos: pago, vencimiento, mora). */
const TRANSICIONES: {
  desde: EstadoInscripcion; hacia: EstadoInscripcion; texto: string; resultado: string; permiso: string;
}[] = [
  { desde: 'pendiente_pago', hacia: 'rechazado', texto: 'Rechazar inscripción', resultado: 'inscripción rechazada',
    permiso: 'inscripciones.gestionar' },
  { desde: 'activo', hacia: 'a_expulsar', texto: 'Marcar para expulsión', resultado: 'marcada para expulsión',
    permiso: 'inscripciones.gestionar' },
  { desde: 'a_expulsar', hacia: 'activo', texto: 'Devolver a activa', resultado: 'la inscripción vuelve a estar activa',
    permiso: 'inscripciones.gestionar' },
  { desde: 'a_expulsar', hacia: 'expulsado', texto: 'Confirmar expulsión', resultado: 'expulsión confirmada',
    permiso: 'expulsion.confirmar' },
];
type Transicion = (typeof TRANSICIONES)[number];

@Component({
  selector: 'app-inscripciones',
  imports: [DatePipe, ReactiveFormsModule, RouterLink, Aviso, Dialogo, PesosPipe, PestanasAlumnos],
  templateUrl: './inscripciones.html',
  styleUrl: './inscripciones.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class InscripcionesPage implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly ruta = inject(ActivatedRoute);
  private readonly router = inject(Router);
  /** Inscripción que pidió abrir la ficha del alumno (?id=…). */
  private abrirAlCargar = this.ruta.snapshot.queryParamMap.get('id');

  // ---------- Permisos (la autorización real la hace el servidor) ----------
  protected readonly esStaff = computed(() => this.auth.tieneAlguno(['alumnos.ver_todos', 'alumnos.ver_rama']));
  protected readonly veTodasLasRamas = computed(() => this.auth.tiene('alumnos.ver_todos'));
  protected readonly puedeInscribir = computed(() => this.auth.tiene('inscripciones.crear'));
  protected readonly puedeAbonar = computed(() => this.auth.tiene('inscripciones.abonar'));
  protected readonly puedeProrrogar = computed(() => this.auth.tiene('prorroga.conceder'));
  protected readonly puedeAnular = computed(() => this.auth.tiene('pagos.anular'));

  protected readonly filtros = FILTROS;
  protected readonly estadoTexto = ESTADO_INSCRIPCION;
  protected readonly hoy = isoLocal(new Date());
  protected readonly limite = LIMITE;

  // ---------- Estado ----------
  protected readonly anio = signal(new Date().getFullYear());
  protected readonly inscripciones = signal<Inscripcion[] | null>(null);
  protected readonly filtro = signal<Filtro>('pendientes');
  protected readonly filtroRama = signal<'' | 'femenina' | 'masculina'>('');
  protected readonly errorCarga = signal(false);
  protected readonly mensaje = signal<{ error: boolean; texto: string } | null>(null);
  protected readonly errorDialogo = signal<string | null>(null);
  protected readonly ocupado = signal(false);

  // ---------- Ventanas emergentes ----------
  protected readonly detalle = signal<Inscripcion | null>(null);
  protected readonly abonando = signal<Inscripcion | null>(null);
  protected readonly prorrogando = signal<Inscripcion | null>(null);
  protected readonly anulando = signal<{ i: Inscripcion; pago: PagoInscripcion } | null>(null);
  protected readonly cambiando = signal<{ i: Inscripcion; t: Transicion } | null>(null);
  protected readonly creando = signal(false);
  protected readonly candidatos = signal<Alumno[] | null>(null);
  protected readonly elegido = signal<Alumno | null>(null);
  private temporizador: ReturnType<typeof setTimeout> | undefined;

  protected readonly formAbono = this.fb.group({
    monto: [0, [Validators.required, Validators.min(1), Validators.max(100_000_000)]],
    fecha_pago: [this.hoy, Validators.required],
  });
  protected readonly formProrroga = this.fb.group({
    nueva_fecha_limite: ['', Validators.required],
    motivo: ['', [Validators.required, Validators.minLength(10), Validators.maxLength(500)]],
  });
  protected readonly formMotivo = this.fb.group({
    motivo: ['', [Validators.minLength(5), Validators.maxLength(500)]],
  });
  protected readonly formNueva = this.fb.group({
    buscar: '',
    pago: this.fb.control<FormaPago>('ninguno'),
    monto: [0],
  });

  // ---------- Derivados ----------
  protected readonly delAnio = computed(() => {
    const r = this.filtroRama();
    return (this.inscripciones() ?? []).filter((i) => !r || i.rama === r);
  });

  protected readonly indicadores = computed(() => {
    const lista = this.delAnio();
    const pendientes = lista.filter((i) => i.estado === 'pendiente_pago');
    return {
      activas: lista.filter((i) => i.estado === 'activo').length,
      pendientes: pendientes.length,
      porCobrar: pendientes.reduce((t, i) => t + i.saldo, 0),
      pronto: pendientes.filter((i) => this.restan(i) <= DIAS_VENCE_PRONTO).length,
      revision: lista.filter((i) => i.estado === 'a_expulsar').length,
      recaudado: lista.reduce((t, i) => t + (i.monto_pagado ?? 0), 0),
    };
  });

  protected readonly conteoFiltro = computed(() => {
    const c: Record<Filtro, number> = { pendientes: 0, pronto: 0, activas: 0, revision: 0, cerradas: 0, todas: 0 };
    for (const f of FILTROS) c[f.valor] = this.aplicarFiltro(f.valor).length;
    return c;
  });

  protected readonly filas = computed(() => this.aplicarFiltro(this.filtro()));
  protected readonly textoFiltro = computed(() => FILTROS.find((f) => f.valor === this.filtro())?.texto ?? '');

  constructor() {
    inject(DestroyRef).onDestroy(() => clearTimeout(this.temporizador));
  }

  ngOnInit(): void {
    // La familia no gestiona: ve todas las de sus hijos.
    if (!this.esStaff()) this.filtro.set('todas');
    this.cargar();
  }

  protected cargar(): void {
    const params = new HttpParams().set('anio', this.anio()).set('limit', LIMITE);
    this.http.get<Inscripcion[]>(`${API}/inscripciones`, { params }).subscribe({
      next: (lista) => {
        this.errorCarga.set(false);
        this.inscripciones.set(lista);
        if (this.abrirAlCargar) {
          const pedida = lista.find((i) => i.id === this.abrirAlCargar);
          this.abrirAlCargar = null;
          if (pedida) this.detalle.set(pedida);
          void this.router.navigate([], { queryParams: {}, replaceUrl: true });
        }
      },
      error: () => this.errorCarga.set(true),
    });
  }

  protected cambiarAnio(delta: number): void {
    this.anio.update((a) => a + delta);
    this.inscripciones.set(null);
    this.cargar();
  }

  private aplicarFiltro(filtro: Filtro): Inscripcion[] {
    const def = FILTROS.find((f) => f.valor === filtro);
    let lista = this.delAnio().filter((i) => !def?.estados || def.estados.includes(i.estado));
    if (filtro === 'pronto') lista = lista.filter((i) => this.restan(i) <= DIAS_VENCE_PRONTO);
    // Lo más urgente primero: menos días para el límite.
    if (filtro === 'pendientes' || filtro === 'pronto') {
      lista = [...lista].sort((a, b) => a.fecha_limite_pago.localeCompare(b.fecha_limite_pago));
    }
    return lista;
  }

  /** Días que faltan para el límite de pago (negativo si ya pasó). */
  protected restan(i: Inscripcion): number {
    return diasEntre(this.hoy, i.fecha_limite_pago);
  }

  protected textoRestan(i: Inscripcion): string {
    const d = this.restan(i);
    if (d < 0) return `venció hace ${-d} d`;
    if (d === 0) return 'vence hoy';
    return `${d} d`;
  }

  protected pct(i: Inscripcion): string {
    return i.valor ? `${Math.round(((i.monto_pagado ?? 0) / i.valor) * 100)}%` : '100%';
  }

  // ---------- Qué se puede hacer con cada inscripción ----------
  protected abonable(i: Inscripcion): boolean {
    return this.puedeAbonar() && i.estado === 'pendiente_pago' && i.saldo > 0;
  }

  protected prorrogable(i: Inscripcion): boolean {
    return this.puedeProrrogar()
      && (i.estado === 'pendiente_pago' || (i.estado === 'rechazado' && i.causa_rechazo === 'vencimiento'));
  }

  protected anulable(i: Inscripcion, p: PagoInscripcion): boolean {
    return this.puedeAnular() && p.monto > 0 && !p.anulado && !['a_expulsar', 'expulsado'].includes(i.estado);
  }

  protected transiciones(i: Inscripcion): Transicion[] {
    return TRANSICIONES.filter((t) => t.desde === i.estado && this.auth.tiene(t.permiso));
  }

  /** Reemplaza la inscripción en la lista y en el detalle abierto. */
  private actualizar(i: Inscripcion): void {
    this.inscripciones.update((lista) => lista?.map((x) => (x.id === i.id ? i : x)) ?? lista);
    if (this.detalle()?.id === i.id) this.detalle.set(i);
  }

  // ---------- Abono ----------
  protected abrirAbono(i: Inscripcion): void {
    this.formAbono.reset({ monto: i.saldo, fecha_pago: this.hoy });
    this.abrir(() => this.abonando.set(i));
  }

  protected guardarAbono(): void {
    const i = this.abonando();
    if (!i) return;
    if (this.formAbono.invalid) return this.errorDialogo.set('Revisa el valor y la fecha del abono.');
    const datos = this.formAbono.getRawValue();
    this.ejecutar(this.http.post<Inscripcion>(`${inscripcionUrl(i.id)}/pagos`, datos), (r) => {
      this.abonando.set(null);
      this.actualizar(r);
      this.avisar(`Abono registrado a ${r.alumno_nombre}. ${resumenPago(r)}`);
    });
  }

  // ---------- Prórroga ----------
  protected abrirProrroga(i: Inscripcion): void {
    this.formProrroga.reset({ nueva_fecha_limite: '', motivo: '' });
    this.abrir(() => this.prorrogando.set(i));
  }

  /** La nueva fecha debe ser posterior a la actual y no estar en el pasado. */
  protected minimoProrroga(i: Inscripcion): string {
    const siguiente = isoLocal(sumarDias(desdeIso(i.fecha_limite_pago), 1));
    return siguiente > this.hoy ? siguiente : this.hoy;
  }

  protected guardarProrroga(): void {
    const i = this.prorrogando();
    if (!i) return;
    if (this.formProrroga.invalid) {
      return this.errorDialogo.set('Indica la nueva fecha y un motivo de al menos 10 caracteres.');
    }
    this.ejecutar(this.http.post<Inscripcion>(`${inscripcionUrl(i.id)}/prorroga`, this.formProrroga.getRawValue()), (r) => {
      this.prorrogando.set(null);
      this.actualizar(r);
      this.avisar(`Prórroga concedida a ${r.alumno_nombre}: ahora paga hasta el ${formatoFecha(r.fecha_limite_pago)}.`);
    });
  }

  // ---------- Anular abono ----------
  protected abrirAnular(i: Inscripcion, pago: PagoInscripcion): void {
    this.formMotivo.reset({ motivo: '' });
    this.abrir(() => this.anulando.set({ i, pago }));
  }

  protected guardarAnulacion(): void {
    const a = this.anulando();
    if (!a) return;
    const motivo = this.formMotivo.getRawValue().motivo.trim();
    if (motivo.length < 10) return this.errorDialogo.set('Explica el motivo (al menos 10 caracteres).');
    const url = `${inscripcionUrl(a.i.id)}/pagos/${encodeURIComponent(a.pago.id)}/anular`;
    this.ejecutar(this.http.post<Inscripcion>(url, { motivo }), (r) => {
      this.anulando.set(null);
      this.actualizar(r);
      this.avisar('Abono anulado. Queda en el historial como un movimiento en negativo.');
    });
  }

  // ---------- Cambio de estado ----------
  protected abrirCambio(i: Inscripcion, t: Transicion): void {
    this.formMotivo.reset({ motivo: '' });
    this.abrir(() => this.cambiando.set({ i, t }));
  }

  /** Rechazar, marcar para expulsión y expulsar piden motivo; devolver a activa no. */
  protected pideMotivo(t: Transicion): boolean {
    return t.hacia !== 'activo';
  }

  protected guardarCambio(): void {
    const c = this.cambiando();
    if (!c) return;
    const motivo = this.formMotivo.getRawValue().motivo.trim();
    if (this.pideMotivo(c.t) && motivo.length < 5) return this.errorDialogo.set('Indica el motivo (al menos 5 caracteres).');
    const cuerpo = { estado: c.t.hacia, motivo: motivo || null };
    this.ejecutar(this.http.post<Inscripcion>(`${inscripcionUrl(c.i.id)}/estado`, cuerpo), (r) => {
      this.cambiando.set(null);
      this.actualizar(r);
      this.avisar(`${r.alumno_nombre}: ${c.t.resultado}.`);
    });
  }

  // ---------- Nueva inscripción ----------
  protected abrirNueva(): void {
    this.formNueva.reset({ buscar: '', pago: 'ninguno', monto: 0 });
    this.candidatos.set(null);
    this.elegido.set(null);
    this.abrir(() => this.creando.set(true));
  }

  /** Busca alumnos activos (con espera, para no pedir en cada tecla). */
  protected buscarAlumno(texto: string): void {
    clearTimeout(this.temporizador);
    this.elegido.set(null);
    if (texto.trim().length < 2) return this.candidatos.set(null);
    this.temporizador = setTimeout(() => {
      const params = new HttpParams().set('buscar', texto.trim()).set('activo', true).set('limit', 20);
      this.http.get<Alumno[]>(`${API}/alumnos`, { params }).subscribe({
        next: (r) => this.candidatos.set(r),
        error: (e) => this.errorDialogo.set(mensajeError(e)),
      });
    }, 300);
  }

  /** Solo se puede inscribir a quien no tiene una inscripción vigente este año. */
  protected inscribible(a: Alumno): boolean {
    return !a.inscripcion_estado || ['rechazado', 'expulsado'].includes(a.inscripcion_estado);
  }

  protected guardarNueva(): void {
    const a = this.elegido();
    if (!a) return this.errorDialogo.set('Elige el alumno que vas a inscribir.');
    const f = this.formNueva.getRawValue();
    const problema = problemaPago(f.pago, f.monto);
    if (problema) return this.errorDialogo.set(problema);
    const peticion = inscribirConPago(this.http, a.id, {
      forma: f.pago, monto: f.monto, hoy: this.hoy, puedeAbonar: this.puedeAbonar(),
    });
    this.ejecutar(peticion, (r) => {
      this.creando.set(false);
      this.cargar();
      this.avisar(`${r.alumno_nombre} quedó inscrito. ${resumenPago(r)}`);
    });
  }

  // ---------- Utilidades ----------
  private abrir(mostrar: () => void): void {
    this.errorDialogo.set(null);
    this.mensaje.set(null);
    mostrar();
  }

  /** Todas las acciones de esta pantalla van en popups: el error se muestra dentro, sin perder lo escrito. */
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
