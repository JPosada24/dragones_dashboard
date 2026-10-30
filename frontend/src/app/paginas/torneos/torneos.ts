import { DatePipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Observable } from 'rxjs';

import { Aviso } from '../../compartido/aviso';
import { Dialogo } from '../../compartido/dialogo';
import { mensajeError } from '../../compartido/errores';
import { diasEntre, isoLocal } from '../../compartido/fechas';
import { PesosPipe } from '../../compartido/pesos.pipe';
import { numeroWhatsApp } from '../../compartido/whatsapp';
import { AuthService } from '../../core/auth/auth.service';
import { API } from '../../core/modelos';
import { Equipo, EstadoEquipo, PagoEquipo, Retiro, Torneo } from './torneos.modelos';

type Filtro = 'proximos' | 'pasados' | 'cancelados';

const ESTADO_EQUIPO: Record<EstadoEquipo, string> = {
  confirmado: 'Confirmado',
  pendiente_pago: 'Pendiente de pago',
  en_espera: 'En lista de espera',
  retirado: 'Retirado',
};

const torneoUrl = (id: string) => `${API}/torneos/${encodeURIComponent(id)}`;

@Component({
  selector: 'app-torneos',
  imports: [DatePipe, ReactiveFormsModule, Aviso, Dialogo, PesosPipe],
  templateUrl: './torneos.html',
  styleUrl: './torneos.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TorneosPage implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly pesos = new PesosPipe();

  protected readonly puedeCobrar = computed(() => this.auth.tiene('pagos.registrar'));
  protected readonly puedeAnular = computed(() => this.auth.tiene('pagos.anular'));
  protected readonly estadoEquipo = ESTADO_EQUIPO;
  protected readonly hoy = isoLocal(new Date());

  protected readonly torneos = signal<Torneo[] | null>(null);
  protected readonly filtro = signal<Filtro>('proximos');
  protected readonly errorCarga = signal(false);
  protected readonly mensaje = signal<{ error: boolean; texto: string } | null>(null);
  protected readonly errorDialogo = signal<string | null>(null);
  protected readonly ocupado = signal(false);

  // ---------- Ventanas emergentes ----------
  protected readonly editando = signal<'nuevo' | Torneo | null>(null);
  protected readonly cancelando = signal<Torneo | null>(null);
  protected readonly eliminando = signal<Torneo | null>(null);
  /** Torneo cuyos clubes se están viendo, con su lista. */
  protected readonly abierto = signal<Torneo | null>(null);
  protected readonly equipos = signal<Equipo[] | null>(null);
  protected readonly inscribiendo = signal(false);
  protected readonly pagando = signal<Equipo | null>(null);
  protected readonly retirando = signal<Equipo | null>(null);
  protected readonly anulando = signal<{ equipo: Equipo; pago: PagoEquipo } | null>(null);

  protected readonly formTorneo = this.fb.group({
    nombre: ['', [Validators.required, Validators.minLength(3), Validators.maxLength(120)]],
    rama: this.fb.control<'' | 'femenina' | 'masculina'>('', Validators.required),
    fecha_inicio: ['', Validators.required],
    fecha_fin: ['', Validators.required],
    fecha_limite_inscripcion: ['', Validators.required],
    lugar: ['', Validators.maxLength(120)],
    cupo_equipos: this.fb.control<number | null>(null, [Validators.min(2), Validators.max(200)]),
    valor_inscripcion: this.fb.control<number | null>(null, [Validators.required, Validators.min(0), Validators.max(100_000_000)]),
  });
  protected readonly formEquipo = this.fb.group({
    nombre_club: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(120)]],
    ciudad: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(80)]],
    delegado_nombre: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(120)]],
    delegado_telefono: ['', [Validators.required, Validators.maxLength(20)]],
    delegado_email: ['', [Validators.email, Validators.maxLength(254)]],
  });
  protected readonly formPago = this.fb.group({
    monto: this.fb.control<number | null>(null, [Validators.required, Validators.min(1), Validators.max(100_000_000)]),
    fecha: [''], // vacía = hoy
  });
  protected readonly formMotivo = this.fb.group({ motivo: ['', Validators.maxLength(255)] });

  // ---------- Derivados ----------
  protected readonly visibles = computed(() => {
    const f = this.filtro();
    const lista = this.torneos() ?? [];
    if (f === 'cancelados') return lista.filter((t) => t.estado === 'cancelado');
    const programados = lista.filter((t) => t.estado === 'programado');
    return f === 'proximos'
      ? programados.filter((t) => t.fecha_fin >= this.hoy)
      : programados.filter((t) => t.fecha_fin < this.hoy).reverse();
  });

  protected readonly conteo = computed(() => {
    const lista = this.torneos() ?? [];
    return {
      proximos: lista.filter((t) => t.estado === 'programado' && t.fecha_fin >= this.hoy).length,
      pasados: lista.filter((t) => t.estado === 'programado' && t.fecha_fin < this.hoy).length,
      cancelados: lista.filter((t) => t.estado === 'cancelado').length,
    };
  });

  protected readonly indicadores = computed(() => {
    const proximos = (this.torneos() ?? []).filter((t) => t.estado === 'programado' && t.fecha_fin >= this.hoy);
    return {
      proximos: proximos.length,
      equipos: proximos.reduce((s, t) => s + t.ocupados, 0),
      enEspera: proximos.reduce((s, t) => s + t.en_espera, 0),
      porCobrar: proximos.reduce((s, t) => s + Math.max(0, t.ocupados * t.valor_inscripcion - t.recaudado), 0),
      recaudado: proximos.reduce((s, t) => s + t.recaudado, 0),
    };
  });

  ngOnInit(): void {
    this.cargar();
  }

  protected cargar(): void {
    this.http.get<Torneo[]>(`${API}/torneos`).subscribe({
      next: (t) => {
        this.errorCarga.set(false);
        this.torneos.set(t);
      },
      error: () => this.errorCarga.set(true),
    });
  }

  // ---------- Presentación ----------
  protected pct(parte: number, total: number): string {
    return total ? `${Math.min(100, Math.round((parte / total) * 100))}%` : '0%';
  }

  protected inscripcionAbierta(t: Torneo): boolean {
    return t.estado === 'programado' && t.fecha_limite_inscripcion >= this.hoy;
  }

  protected cierre(t: Torneo): string {
    const d = diasEntre(this.hoy, t.fecha_limite_inscripcion);
    if (d < 0) return 'inscripciones cerradas';
    return d === 0 ? 'cierra hoy' : `cierra en ${d} d`;
  }

  protected whatsapp(e: Equipo): string | null {
    const n = numeroWhatsApp(e.delegado_telefono);
    return n ? `https://wa.me/${n}` : null;
  }

  protected anulado(e: Equipo, pago: PagoEquipo): boolean {
    return e.pagos.some((x) => x.anula_id === pago.id);
  }

  // ---------- Torneo: crear / editar ----------
  protected abrirNuevo(): void {
    this.formTorneo.reset();
    this.abrir(() => this.editando.set('nuevo'));
  }

  protected abrirEditar(t: Torneo): void {
    this.formTorneo.reset({
      nombre: t.nombre, rama: t.rama, fecha_inicio: t.fecha_inicio, fecha_fin: t.fecha_fin,
      fecha_limite_inscripcion: t.fecha_limite_inscripcion, lugar: t.lugar ?? '', cupo_equipos: t.cupo_equipos,
      valor_inscripcion: t.valor_inscripcion,
    });
    this.abrir(() => this.editando.set(t));
  }

  protected guardarTorneo(): void {
    const modo = this.editando();
    if (!modo) return;
    if (this.formTorneo.invalid) return this.errorDialogo.set('Completa nombre, rama, fechas y valor de la inscripción.');
    const f = this.formTorneo.getRawValue();
    const cuerpo = { ...f, lugar: f.lugar.trim() || null, cupo_equipos: f.cupo_equipos ?? undefined };
    const peticion = modo === 'nuevo'
      ? this.http.post<Torneo>(`${API}/torneos`, cuerpo)
      : this.http.patch<Torneo>(torneoUrl(modo.id), cuerpo);
    this.ejecutar(peticion, (t) => {
      this.editando.set(null);
      this.cargar();
      this.avisar(modo === 'nuevo'
        ? `«${t.nombre}» creado. Los entrenamientos de esas fechas se cancelan solos.`
        : `«${t.nombre}» actualizado.`);
    });
  }

  protected abrirCancelar(t: Torneo): void {
    this.formMotivo.reset();
    this.abrir(() => this.cancelando.set(t));
  }

  protected guardarCancelacion(): void {
    const t = this.cancelando();
    if (!t) return;
    const motivo = this.formMotivo.getRawValue().motivo.trim() || null;
    this.ejecutar(this.http.post<Torneo>(`${torneoUrl(t.id)}/cancelar`, { motivo }), () => {
      this.cancelando.set(null);
      this.cargar();
      this.avisar(`«${t.nombre}» cancelado. Los entrenamientos de esos días vuelven.`);
    });
  }

  protected abrirEliminar(t: Torneo): void {
    this.abrir(() => this.eliminando.set(t));
  }

  protected eliminar(): void {
    const t = this.eliminando();
    if (!t) return;
    this.ejecutar(this.http.delete(torneoUrl(t.id)), () => {
      this.eliminando.set(null);
      this.cargar();
      this.avisar(`«${t.nombre}» eliminado.`);
    });
  }

  // ---------- Clubes ----------
  protected verEquipos(t: Torneo): void {
    this.equipos.set(null);
    this.abrir(() => this.abierto.set(t));
    this.cargarEquipos(t);
  }

  private cargarEquipos(t: Torneo): void {
    this.http.get<Equipo[]>(`${torneoUrl(t.id)}/equipos`).subscribe({
      next: (e) => this.equipos.set(e),
      error: (e) => this.errorDialogo.set(mensajeError(e)),
    });
  }

  /** Tras un cambio en un club: refresca la lista y los totales del torneo. */
  private refrescar(t: Torneo): void {
    this.cargarEquipos(t);
    this.http.get<Torneo>(torneoUrl(t.id)).subscribe((nuevo) => {
      this.torneos.update((l) => l?.map((x) => (x.id === nuevo.id ? nuevo : x)) ?? l);
      if (this.abierto()?.id === nuevo.id) this.abierto.set(nuevo);
    });
  }

  protected abrirInscribir(): void {
    this.formEquipo.reset();
    this.errorDialogo.set(null);
    this.inscribiendo.set(true);
  }

  protected guardarEquipo(): void {
    const t = this.abierto();
    if (!t) return;
    if (this.formEquipo.invalid) return this.errorDialogo.set('Completa el club, la ciudad y el delegado con su teléfono.');
    const f = this.formEquipo.getRawValue();
    const cuerpo = { ...f, delegado_email: f.delegado_email.trim() || null };
    this.ejecutar(this.http.post<Equipo>(`${torneoUrl(t.id)}/equipos`, cuerpo), (e) => {
      this.inscribiendo.set(false);
      this.refrescar(t);
      this.avisar(e.estado === 'en_espera'
        ? `${e.nombre_club} quedó en lista de espera: el cupo está lleno.`
        : `${e.nombre_club} inscrito.`);
    });
  }

  protected abrirPago(e: Equipo): void {
    this.formPago.reset();
    this.errorDialogo.set(null);
    this.pagando.set(e);
  }

  protected guardarPago(): void {
    const t = this.abierto();
    const e = this.pagando();
    if (!t || !e) return;
    if (this.formPago.invalid) return this.errorDialogo.set('Escribe el valor del pago.');
    const { monto, fecha } = this.formPago.getRawValue();
    const url = `${torneoUrl(t.id)}/equipos/${encodeURIComponent(e.id)}/pagos`;
    this.ejecutar(this.http.post<Equipo>(url, { monto, fecha: fecha || this.hoy }), (r) => {
      this.pagando.set(null);
      this.refrescar(t);
      this.avisar(r.estado === 'confirmado'
        ? `${r.nombre_club} pagó completo: queda confirmado.`
        : `Pago registrado. Saldo de ${r.nombre_club}: ${this.pesos.transform(r.saldo)}.`);
    });
  }

  protected abrirRetirar(e: Equipo): void {
    this.formMotivo.reset();
    this.errorDialogo.set(null);
    this.retirando.set(e);
  }

  protected guardarRetiro(): void {
    const t = this.abierto();
    const e = this.retirando();
    if (!t || !e) return;
    const motivo = this.formMotivo.getRawValue().motivo.trim() || null;
    const url = `${torneoUrl(t.id)}/equipos/${encodeURIComponent(e.id)}/retirar`;
    this.ejecutar(this.http.post<Retiro>(url, { motivo }), (r) => {
      this.retirando.set(null);
      this.refrescar(t);
      this.avisar(r.promovido
        ? `${e.nombre_club} se retiró; entra ${r.promovido.nombre_club} desde la lista de espera.`
        : `${e.nombre_club} se retiró del torneo.`);
    });
  }

  protected abrirAnular(equipo: Equipo, pago: PagoEquipo): void {
    this.formMotivo.reset();
    this.errorDialogo.set(null);
    this.anulando.set({ equipo, pago });
  }

  protected guardarAnulacion(): void {
    const t = this.abierto();
    const a = this.anulando();
    if (!t || !a) return;
    const motivo = this.formMotivo.getRawValue().motivo.trim() || null;
    const url = `${torneoUrl(t.id)}/equipos/${encodeURIComponent(a.equipo.id)}/pagos/${encodeURIComponent(a.pago.id)}/anular`;
    this.ejecutar(this.http.post<Equipo>(url, { motivo }), () => {
      this.anulando.set(null);
      this.refrescar(t);
      this.avisar('Pago anulado: queda en el historial como un movimiento en negativo.');
    });
  }

  // ---------- Utilidades ----------
  private abrir(mostrar: () => void): void {
    this.errorDialogo.set(null);
    this.mensaje.set(null);
    mostrar();
  }

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
