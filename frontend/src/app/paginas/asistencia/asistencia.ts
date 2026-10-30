import { DatePipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Observable } from 'rxjs';

import { mensajeError } from '../../compartido/errores';
import { desdeIso, diaSemana, isoLocal, lunesDe, sumarDias } from '../../compartido/fechas';
import { AuthService } from '../../core/auth/auth.service';
import { API } from '../../core/modelos';
import {
  AlertaInasistencia, EstadoAsistencia, FilaPlanilla, Justificacion, Marca, Rama, Sesion,
} from './asistencia.modelos';

const DIAS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];

const ESTADO: Record<EstadoAsistencia, string> = {
  presente: 'Presente',
  ausente: 'Ausente',
  justificado: 'Justificado',
};

const sesionUrl = (id: string) => `${API}/sesiones/${encodeURIComponent(id)}`;

@Component({
  selector: 'app-asistencia',
  imports: [DatePipe, ReactiveFormsModule],
  templateUrl: './asistencia.html',
  styleUrl: './asistencia.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AsistenciaPage implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private readonly fb = inject(FormBuilder).nonNullable;

  // ---------- Permisos (la autorización real la hace el servidor) ----------
  protected readonly esStaff = computed(() => this.auth.tieneAlguno(['alumnos.ver_todos', 'alumnos.ver_rama']));
  protected readonly veTodasLasRamas = computed(() => this.auth.tiene('alumnos.ver_todos'));
  protected readonly puedeMarcar = computed(() => this.auth.tiene('asistencia.marcar_grupo'));
  protected readonly puedeCorregir = computed(() => this.auth.tiene('asistencia.corregir'));
  protected readonly puedeRevisar = computed(() => this.auth.tiene('justificaciones.revisar'));
  protected readonly puedeGestionar = computed(() => this.auth.tiene('sesiones.gestionar'));
  protected readonly esFamilia = computed(() => this.auth.tiene('asistencia.marcar_propia') && !this.puedeMarcar());

  protected readonly dias = DIAS;
  protected readonly estadoTexto = ESTADO;
  protected readonly hoy = isoLocal(new Date());

  // ---------- Estado ----------
  protected readonly lunes = signal(lunesDe(new Date()));
  protected readonly rama = signal<Rama | ''>('');
  protected readonly sesiones = signal<Sesion[] | null>(null);
  protected readonly seleccionadaId = signal<string | null>(null);
  protected readonly planilla = signal<FilaPlanilla[] | null>(null);
  /** Marcas sin guardar: alumno_id → presente/ausente. */
  protected readonly cambios = signal<Record<string, Marca>>({});
  protected readonly justificaciones = signal<Justificacion[]>([]);
  protected readonly alertas = signal<AlertaInasistencia[]>([]);

  protected readonly mensaje = signal<{ error: boolean; texto: string } | null>(null);
  protected readonly ocupado = signal(false);
  protected readonly errorCarga = signal(false);

  // Formularios en línea (uno abierto a la vez por tipo).
  protected readonly corrigiendo = signal<string | null>(null);
  protected readonly justificando = signal<string | null>(null);
  protected readonly rechazando = signal<string | null>(null);
  protected readonly cancelandoSesion = signal(false);
  protected readonly programando = signal(false);

  protected readonly formCorregir = this.fb.group({
    estado: this.fb.control<EstadoAsistencia>('presente'),
    motivo: ['', [Validators.required, Validators.minLength(10), Validators.maxLength(255)]],
  });
  protected readonly formJustificar = this.fb.group({
    motivo: ['', [Validators.required, Validators.minLength(10), Validators.maxLength(500)]],
  });
  protected readonly formRechazar = this.fb.group({
    comentario: ['', [Validators.required, Validators.minLength(3), Validators.maxLength(255)]],
  });
  protected readonly formCancelar = this.fb.group({
    motivo: ['', [Validators.required, Validators.minLength(5), Validators.maxLength(255)]],
  });
  protected readonly formProgramar = this.fb.group({
    rama: this.fb.control<Rama>('femenina', Validators.required),
    desde: [this.hoy, Validators.required],
    hasta: [''],
    dias: this.fb.control<number[]>([]),
    hora_inicio: ['18:00', Validators.required],
    hora_fin: ['20:00', Validators.required],
    lugar: ['', Validators.maxLength(120)],
  });

  // ---------- Derivados ----------
  protected readonly domingo = computed(() => sumarDias(this.lunes(), 6));
  protected readonly seleccionada = computed(
    () => this.sesiones()?.find((s) => s.id === this.seleccionadaId()) ?? null,
  );
  /** Se puede marcar en grupo: sesión abierta, no cancelada y no futura. */
  protected readonly marcable = computed(() => {
    const s = this.seleccionada();
    return !!s && this.puedeMarcar() && !s.cancelada && !s.cerrada && s.fecha <= this.hoy;
  });
  protected readonly hayCambios = computed(() => Object.keys(this.cambios()).length > 0);
  protected readonly conteo = computed(() => {
    const c = { presente: 0, justificado: 0, ausente: 0, sin_marcar: 0 };
    for (const f of this.planilla() ?? []) {
      const e = this.estadoDe(f);
      if (e) c[e]++;
      else c.sin_marcar++;
    }
    return c;
  });

  ngOnInit(): void {
    const u = this.auth.usuario();
    if (u?.rama) this.formProgramar.controls.rama.setValue(u.rama);
    if (u?.rama && !this.veTodasLasRamas()) this.formProgramar.controls.rama.disable();
    this.cargarSesiones(true);
    this.cargarJustificaciones();
    if (this.esStaff()) {
      this.http.get<AlertaInasistencia[]>(`${API}/sesiones/alertas`).subscribe({
        next: (a) => this.alertas.set(a),
        error: () => undefined,
      });
    }
  }

  // ---------- Carga ----------
  protected cambiarSemana(semanas: number): void {
    this.lunes.set(sumarDias(this.lunes(), semanas * 7));
    this.cargarSesiones(true);
  }

  protected irAHoy(): void {
    this.lunes.set(lunesDe(new Date()));
    this.cargarSesiones(true);
  }

  protected cambiarRama(valor: string): void {
    this.rama.set(valor === 'masculina' || valor === 'femenina' ? valor : '');
    this.cargarSesiones(true);
  }

  /** `elegir`: seleccionar de nuevo una sesión (la de hoy si la hay) en vez de conservar la actual. */
  private cargarSesiones(elegir: boolean): void {
    const params: Record<string, string> = { desde: isoLocal(this.lunes()), hasta: isoLocal(this.domingo()) };
    if (this.rama()) params['rama'] = this.rama();
    this.http.get<Sesion[]>(`${API}/sesiones`, { params }).subscribe({
      next: (lista) => {
        const ordenadas = [...lista].sort((a, b) => (a.fecha + a.hora_inicio).localeCompare(b.fecha + b.hora_inicio));
        this.sesiones.set(ordenadas);
        this.errorCarga.set(false);
        const actual = this.seleccionadaId();
        if (elegir || !ordenadas.some((s) => s.id === actual)) {
          const activas = ordenadas.filter((s) => !s.cancelada);
          const preferida =
            activas.find((s) => s.fecha === this.hoy) ??
            [...activas].reverse().find((s) => s.fecha < this.hoy) ??
            activas[0] ??
            null;
          this.seleccionar(preferida);
        }
      },
      error: () => this.errorCarga.set(true),
    });
  }

  protected seleccionar(s: Sesion | null): void {
    this.seleccionadaId.set(s?.id ?? null);
    this.cambios.set({});
    this.cerrarFormularios();
    this.planilla.set(null);
    if (!s) return;
    this.http.get<FilaPlanilla[]>(`${sesionUrl(s.id)}/asistencia`).subscribe({
      next: (p) => {
        if (this.seleccionadaId() === s.id) this.planilla.set(p);
      },
      error: (e) => this.avisar(e),
    });
  }

  private cargarJustificaciones(): void {
    // El staff que revisa ve las pendientes; la familia ve el historial de las suyas.
    if (!this.puedeRevisar() && !this.esFamilia()) return;
    const params: Record<string, string | number> = this.puedeRevisar() ? { estado: 'pendiente' } : { limit: 10 };
    this.http.get<Justificacion[]>(`${API}/justificaciones`, { params }).subscribe({
      next: (j) => this.justificaciones.set(j),
      error: () => undefined,
    });
  }

  // ---------- Planilla ----------
  protected estadoDe(f: FilaPlanilla): EstadoAsistencia | null {
    return this.cambios()[f.alumno_id] ?? f.asistencia;
  }

  protected marcar(f: FilaPlanilla, marca: Marca): void {
    this.cambios.update((c) => {
      const nuevo = { ...c };
      if (f.asistencia === marca) delete nuevo[f.alumno_id];
      else nuevo[f.alumno_id] = marca;
      return nuevo;
    });
  }

  /** Marca como presentes a quienes aún no tienen marca. */
  protected todosPresentes(): void {
    const nuevo = { ...this.cambios() };
    for (const f of this.planilla() ?? []) {
      if (!this.estadoDe(f)) nuevo[f.alumno_id] = 'presente';
    }
    this.cambios.set(nuevo);
  }

  protected descartar(): void {
    this.cambios.set({});
  }

  protected guardar(): void {
    const s = this.seleccionada();
    if (!s || !this.hayCambios()) return;
    const marcas = Object.entries(this.cambios()).map(([alumno_id, estado]) => ({ alumno_id, estado }));
    this.ejecutar(this.http.post<FilaPlanilla[]>(`${sesionUrl(s.id)}/asistencia`, { marcas }), (p) => {
      this.planilla.set(p);
      this.cambios.set({});
      this.avisar(null, `Planilla guardada (${marcas.length} ${marcas.length === 1 ? 'marca' : 'marcas'}).`);
    });
  }

  /** La familia marca "presente" para su hijo (solo el día y en el horario). */
  protected marcarPropia(f: FilaPlanilla): void {
    const s = this.seleccionada();
    if (!s) return;
    this.ejecutar(this.http.post<void>(`${sesionUrl(s.id)}/asistencia/propia`, { alumno_id: f.alumno_id }), () => {
      this.recargarPlanilla();
      this.avisar(null, `Asistencia de ${f.alumno_nombre} registrada.`);
    });
  }

  protected puedeJustificar(f: FilaPlanilla): boolean {
    const s = this.seleccionada();
    return (
      !!s && !s.cancelada && (this.esFamilia() || this.puedeMarcar()) && f.asistencia !== 'presente' &&
      f.justificacion !== 'pendiente' && f.justificacion !== 'aprobada'
    );
  }

  protected puedeMarcarPropia(f: FilaPlanilla): boolean {
    const s = this.seleccionada();
    return !!s && this.esFamilia() && !s.cancelada && !s.cerrada && s.fecha === this.hoy && f.asistencia === null;
  }

  // ---------- Formularios en línea ----------
  protected abrirCorregir(f: FilaPlanilla): void {
    this.cerrarFormularios();
    this.formCorregir.reset({ estado: f.asistencia === 'presente' ? 'ausente' : 'presente', motivo: '' });
    this.corrigiendo.set(f.alumno_id);
  }

  protected enviarCorreccion(f: FilaPlanilla): void {
    const s = this.seleccionada();
    if (!s || this.formCorregir.invalid) return;
    const url = `${sesionUrl(s.id)}/asistencia/${encodeURIComponent(f.alumno_id)}`;
    this.ejecutar(this.http.patch<FilaPlanilla[]>(url, this.formCorregir.getRawValue()), (p) => {
      this.planilla.set(p);
      this.corrigiendo.set(null);
      this.avisar(null, `Asistencia de ${f.alumno_nombre} corregida.`);
    });
  }

  protected abrirJustificar(f: FilaPlanilla): void {
    this.cerrarFormularios();
    this.formJustificar.reset();
    this.justificando.set(f.alumno_id);
  }

  protected enviarJustificacion(f: FilaPlanilla): void {
    const s = this.seleccionada();
    if (!s || this.formJustificar.invalid) return;
    const cuerpo = { alumno_id: f.alumno_id, motivo: this.formJustificar.getRawValue().motivo };
    this.ejecutar(this.http.post<Justificacion>(`${sesionUrl(s.id)}/justificaciones`, cuerpo), () => {
      this.justificando.set(null);
      this.recargarPlanilla();
      this.cargarJustificaciones();
      this.avisar(null, 'Justificación enviada. El club la revisará.');
    });
  }

  protected revisar(j: Justificacion, aprobar: boolean): void {
    if (!aprobar && this.formRechazar.invalid) return;
    const cuerpo = aprobar ? { aprobar: true } : { aprobar: false, comentario: this.formRechazar.getRawValue().comentario };
    this.ejecutar(this.http.post<Justificacion>(`${API}/justificaciones/${encodeURIComponent(j.id)}/revisar`, cuerpo), () => {
      this.justificaciones.update((l) => l.filter((x) => x.id !== j.id));
      this.rechazando.set(null);
      if (this.seleccionadaId() === j.sesion_id) this.recargarPlanilla();
      this.avisar(null, aprobar ? `Justificación de ${j.alumno_nombre} aprobada.` : `Justificación de ${j.alumno_nombre} rechazada.`);
    });
  }

  protected abrirRechazo(j: Justificacion): void {
    this.formRechazar.reset();
    this.rechazando.set(j.id);
  }

  protected cancelarSesion(): void {
    const s = this.seleccionada();
    if (!s || this.formCancelar.invalid) return;
    this.ejecutar(this.http.post<Sesion>(`${sesionUrl(s.id)}/cancelar`, this.formCancelar.getRawValue()), (actualizada) => {
      this.sesiones.update((l) => l?.map((x) => (x.id === actualizada.id ? actualizada : x)) ?? l);
      this.cancelandoSesion.set(false);
      this.avisar(null, 'Sesión cancelada.');
    });
  }

  protected alternarDia(dia: number): void {
    const c = this.formProgramar.controls.dias;
    c.setValue(c.value.includes(dia) ? c.value.filter((d) => d !== dia) : [...c.value, dia].sort());
  }

  /** Una fecha → una sesión; un rango → se programan los días elegidos. */
  protected programar(): void {
    if (this.formProgramar.invalid) return;
    const v = this.formProgramar.getRawValue();
    const horario = { rama: v.rama, hora_inicio: v.hora_inicio, hora_fin: v.hora_fin, lugar: v.lugar.trim() || null };
    const rango = !!v.hasta && v.hasta !== v.desde;
    if (rango && v.dias.length === 0) {
      this.avisar(null, 'Elige al menos un día de la semana para programar el rango.', true);
      return;
    }
    const peticion: Observable<Sesion | Sesion[]> = rango
      ? this.http.post<Sesion[]>(`${API}/sesiones/programar`, { ...horario, desde: v.desde, hasta: v.hasta, dias_semana: v.dias })
      : this.http.post<Sesion>(`${API}/sesiones`, { ...horario, fecha: v.desde });
    this.ejecutar(peticion, (r) => {
      const n = Array.isArray(r) ? r.length : 1;
      this.programando.set(false);
      this.lunes.set(lunesDe(desdeIso(v.desde)));
      this.cargarSesiones(true);
      this.avisar(null, n === 1 ? 'Sesión programada.' : `${n} sesiones programadas.`);
    });
  }

  protected abrirProgramar(): void {
    this.cerrarFormularios();
    this.programando.set(!this.programando());
  }

  // ---------- Apoyo ----------
  protected diaCorto(iso: string): string {
    return DIAS[diaSemana(desdeIso(iso))] ?? '';
  }

  protected hora(h: string): string {
    return h.slice(0, 5);
  }

  protected pct(n: number): string {
    const total = this.planilla()?.length ?? 0;
    return total ? `${Math.round((n / total) * 100)}%` : '0%';
  }

  private recargarPlanilla(): void {
    const id = this.seleccionadaId();
    if (!id) return;
    this.http.get<FilaPlanilla[]>(`${sesionUrl(id)}/asistencia`).subscribe({
      next: (p) => {
        if (this.seleccionadaId() === id) this.planilla.set(p);
      },
      error: (e) => this.avisar(e),
    });
  }

  private cerrarFormularios(): void {
    this.corrigiendo.set(null);
    this.justificando.set(null);
    this.cancelandoSesion.set(false);
    this.programando.set(false);
  }

  /** Ejecuta una acción mostrando el estado ocupado y el error de la API si falla. */
  private ejecutar<T>(peticion: Observable<T>, ok: (r: T) => void): void {
    this.ocupado.set(true);
    this.mensaje.set(null);
    peticion.subscribe({
      next: (r) => {
        this.ocupado.set(false);
        ok(r);
      },
      error: (e) => {
        this.ocupado.set(false);
        this.avisar(e);
      },
    });
  }

  private avisar(e: unknown, texto?: string, error = false): void {
    this.mensaje.set(e ? { error: true, texto: mensajeError(e) } : { error, texto: texto ?? '' });
  }
}
