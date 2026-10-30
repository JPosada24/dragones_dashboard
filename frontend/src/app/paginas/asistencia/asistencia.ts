import { DatePipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Observable } from 'rxjs';

import { Aviso } from '../../compartido/aviso';
import { Dialogo } from '../../compartido/dialogo';
import { mensajeError } from '../../compartido/errores';
import { desdeIso, diaSemana, isoLocal, lunesDe, sumarDias } from '../../compartido/fechas';
import { AuthService } from '../../core/auth/auth.service';
import { API } from '../../core/modelos';
import {
  AlertaInasistencia, EstadoAsistencia, FilaPlanilla, Horario, HorarioActualizado, Justificacion, Marca, Rama, Sesion,
} from './asistencia.modelos';

const DIAS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom'];
const DIAS_LARGOS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];

const ESTADO: Record<EstadoAsistencia, string> = {
  presente: 'Presente',
  ausente: 'Ausente',
  justificado: 'Justificado',
};

const CANCELACION: Record<string, string> = {
  festivo: 'festivo',
  torneo: 'torneo',
  horario: 'sin entreno',
  manual: 'cancelada',
};

const sesionUrl = (id: string) => `${API}/sesiones/${encodeURIComponent(id)}`;

@Component({
  selector: 'app-asistencia',
  imports: [DatePipe, ReactiveFormsModule, Aviso, Dialogo],
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
  protected readonly diasLargos = DIAS_LARGOS;
  protected readonly estadoTexto = ESTADO;
  protected readonly hoy = isoLocal(new Date());
  protected readonly opcionesRama: { v: Rama | ''; t: string }[] = [
    { v: '', t: 'Todos' }, { v: 'femenina', t: 'Femenina' }, { v: 'masculina', t: 'Masculina' },
  ];

  // ---------- Estado ----------
  protected readonly lunes = signal(lunesDe(new Date()));
  protected readonly sesiones = signal<Sesion[] | null>(null);
  protected readonly seleccionadaId = signal<string | null>(null);
  protected readonly planilla = signal<FilaPlanilla[] | null>(null);
  protected readonly filtroRama = signal<Rama | ''>('');
  /** Marcas sin guardar: alumno_id → presente/ausente. */
  protected readonly cambios = signal<Record<string, Marca>>({});
  protected readonly horario = signal<Horario | null>(null);
  protected readonly justificaciones = signal<Justificacion[]>([]);
  protected readonly alertas = signal<AlertaInasistencia[]>([]);

  protected readonly mensaje = signal<{ error: boolean; texto: string } | null>(null);
  protected readonly errorDialogo = signal<string | null>(null);
  protected readonly ocupado = signal(false);
  protected readonly errorCarga = signal(false);

  // Ventanas emergentes (popups).
  protected readonly editandoHorario = signal(false);
  protected readonly creandoExtra = signal(false);
  protected readonly cancelandoSesion = signal(false);
  protected readonly eliminandoSesion = signal(false);
  protected readonly corrigiendo = signal<FilaPlanilla | null>(null);
  protected readonly justificando = signal<FilaPlanilla | null>(null);
  protected readonly rechazando = signal<Justificacion | null>(null);

  protected readonly formHorario = this.fb.group({
    dias: this.fb.array(
      DIAS.map(() =>
        this.fb.group({
          activo: false,
          hora_inicio: [''],
          hora_fin: [''],
          lugar: ['', Validators.maxLength(120)],
        }),
      ),
    ),
  });
  protected readonly formExtra = this.fb.group({
    fecha: ['', Validators.required],
    hora_inicio: ['', Validators.required],
    hora_fin: ['', Validators.required],
    lugar: ['', Validators.maxLength(120)],
  });
  protected readonly formCorregir = this.fb.group({
    estado: this.fb.control<EstadoAsistencia | ''>('', Validators.required),
    motivo: ['', [Validators.required, Validators.minLength(10), Validators.maxLength(255)]],
  });
  protected readonly formJustificar = this.fb.group({
    motivo: ['', [Validators.required, Validators.minLength(10), Validators.maxLength(500)]],
  });
  protected readonly formRechazar = this.fb.group({
    comentario: ['', [Validators.required, Validators.minLength(3), Validators.maxLength(255)]],
  });
  protected readonly formCancelar = this.fb.group({ motivo: ['', Validators.maxLength(255)] });

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
  /** Filas que se muestran (Admin/SA pueden filtrar por rama; el servidor ya limita al Entrenador y la familia). */
  protected readonly filas = computed(() => {
    const r = this.filtroRama();
    return (this.planilla() ?? []).filter((f) => !r || f.rama === r);
  });
  protected readonly hayCambios = computed(() => Object.keys(this.cambios()).length > 0);
  protected readonly conteo = computed(() => {
    const c = { presente: 0, justificado: 0, ausente: 0, sin_marcar: 0 };
    for (const f of this.filas()) {
      const e = this.estadoDe(f);
      if (e) c[e]++;
      else c.sin_marcar++;
    }
    return c;
  });

  ngOnInit(): void {
    this.cargarSesiones(true);
    this.cargarHorario();
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

  /** `elegir`: seleccionar de nuevo una sesión (la de hoy si la hay) en vez de conservar la actual. */
  private cargarSesiones(elegir: boolean): void {
    const params = { desde: isoLocal(this.lunes()), hasta: isoLocal(this.domingo()) };
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
            ordenadas[0] ??
            null;
          this.seleccionar(preferida);
        }
      },
      error: () => this.errorCarga.set(true),
    });
  }

  private cargarHorario(): void {
    this.http.get<Horario>(`${API}/sesiones/horario`).subscribe({
      next: (h) => this.horario.set(h),
      error: () => undefined,
    });
  }

  protected seleccionar(s: Sesion | null): void {
    this.seleccionadaId.set(s?.id ?? null);
    this.cambios.set({});
    this.planilla.set(null);
    if (s && !s.cancelada) this.recargarPlanilla(); // una cancelada no tiene planilla
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
    // Volver a la marca guardada quita el cambio pendiente.
    this.cambios.update((c) => {
      const resto = Object.fromEntries(Object.entries(c).filter(([id]) => id !== f.alumno_id));
      return f.asistencia === marca ? resto : { ...resto, [f.alumno_id]: marca };
    });
  }

  /** Marca como presentes a quienes aún no tienen marca (de las filas visibles). */
  protected todosPresentes(): void {
    const nuevo = { ...this.cambios() };
    for (const f of this.filas()) {
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
    this.ejecutar(this.http.post(`${sesionUrl(s.id)}/asistencia/propia`, { alumno_id: f.alumno_id }), () => {
      this.recargarPlanilla();
      this.avisar(null, `Asistencia de ${f.alumno_nombre} registrada.`);
    });
  }

  protected puedeJustificar(f: FilaPlanilla): boolean {
    const s = this.seleccionada();
    return (
      !!s && !s.cancelada && (this.esFamilia() || this.puedeMarcar()) && f.asistencia !== 'presente' &&
      this.estadoDe(f) !== 'presente' && f.justificacion !== 'pendiente' && f.justificacion !== 'aprobada'
    );
  }

  protected puedeMarcarPropia(f: FilaPlanilla): boolean {
    const s = this.seleccionada();
    return !!s && this.esFamilia() && !s.cancelada && !s.cerrada && s.fecha === this.hoy && f.asistencia === null;
  }

  // ---------- Popups ----------
  protected abrirHorario(): void {
    const dias = this.horario()?.dias ?? [];
    this.formHorario.controls.dias.controls.forEach((g, i) => {
      const d = dias.find((x) => x.dia_semana === i);
      g.reset({
        activo: !!d,
        hora_inicio: d ? this.hora(d.hora_inicio) : '',
        hora_fin: d ? this.hora(d.hora_fin) : '',
        lugar: d?.lugar ?? '',
      });
    });
    this.abrir(() => this.editandoHorario.set(true));
  }

  protected guardarHorario(): void {
    const dias = this.formHorario.getRawValue().dias.flatMap((d, i) =>
      d.activo ? [{ dia_semana: i, hora_inicio: d.hora_inicio, hora_fin: d.hora_fin, lugar: d.lugar.trim() || null }] : [],
    );
    if (dias.some((d) => !d.hora_inicio || !d.hora_fin)) {
      this.errorDialogo.set('Indica la hora de inicio y de fin de cada día de entrenamiento.');
      return;
    }
    if (dias.some((d) => d.hora_fin <= d.hora_inicio)) {
      this.errorDialogo.set('En cada día, la hora de fin debe ser posterior a la de inicio.');
      return;
    }
    this.ejecutar(this.http.put<HorarioActualizado>(`${API}/sesiones/horario`, { dias }), (r) => {
      this.horario.set(r);
      this.editandoHorario.set(false);
      this.cargarSesiones(false);
      const partes = [`${r.creadas} nuevas`];
      if (r.eliminadas) partes.push(`${r.eliminadas} quitadas`);
      if (r.canceladas) partes.push(`${r.canceladas} canceladas (tenían registros)`);
      this.avisar(null, `Horario guardado. Sesiones: ${partes.join(', ')}.`);
    }, true);
  }

  protected abrirExtra(): void {
    this.formExtra.reset({ fecha: '', hora_inicio: '', hora_fin: '', lugar: '' });
    this.abrir(() => this.creandoExtra.set(true));
  }

  protected crearExtra(): void {
    if (this.formExtra.invalid) return this.errorDialogo.set('Indica la fecha y las horas de inicio y fin.');
    const v = this.formExtra.getRawValue();
    const cuerpo = { ...v, lugar: v.lugar.trim() || null };
    this.ejecutar(this.http.post<Sesion>(`${API}/sesiones`, cuerpo), (s) => {
      this.creandoExtra.set(false);
      this.lunes.set(lunesDe(desdeIso(s.fecha)));
      this.cargarSesiones(false);
      this.seleccionar(s);
      this.avisar(null, 'Sesión extra creada.');
    }, true);
  }

  protected abrirCancelar(): void {
    this.formCancelar.reset();
    this.abrir(() => this.cancelandoSesion.set(true));
  }

  protected cancelarSesion(): void {
    const s = this.seleccionada();
    if (!s || this.formCancelar.invalid) return;
    const motivo = this.formCancelar.getRawValue().motivo.trim() || null;
    this.ejecutar(this.http.post<Sesion>(`${sesionUrl(s.id)}/cancelar`, { motivo }), (actualizada) => {
      this.sesiones.update((l) => l?.map((x) => (x.id === actualizada.id ? actualizada : x)) ?? l);
      this.cancelandoSesion.set(false);
      this.avisar(null, 'Sesión cancelada.');
    }, true);
  }

  protected abrirEliminar(): void {
    this.abrir(() => this.eliminandoSesion.set(true));
  }

  /** Solo las sesiones extra (creadas a mano); las del horario se cancelan. */
  protected eliminarSesion(): void {
    const s = this.seleccionada();
    if (!s) return;
    this.ejecutar(this.http.delete(sesionUrl(s.id)), () => {
      this.eliminandoSesion.set(false);
      this.sesiones.update((l) => l?.filter((x) => x.id !== s.id) ?? l);
      this.seleccionar(this.sesiones()?.[0] ?? null);
      this.avisar(null, 'Sesión extra eliminada.');
    }, true);
  }

  /** Se puede deshacer una cancelación manual o por festivo, mientras no haya pasado el día (el servidor
   * además exige que no haya pasado la hora de cierre). Torneos y cambios de horario se manejan solos. */
  protected reactivable(s: Sesion): boolean {
    return (
      this.puedeGestionar() && s.cancelada && !s.cerrada && s.fecha >= this.hoy &&
      (s.causa_cancelacion === 'manual' || s.causa_cancelacion === 'festivo')
    );
  }

  protected reactivar(s: Sesion): void {
    this.ejecutar(this.http.post<Sesion>(`${sesionUrl(s.id)}/reactivar`, {}), (actualizada) => {
      this.sesiones.update((l) => l?.map((x) => (x.id === actualizada.id ? actualizada : x)) ?? l);
      this.recargarPlanilla();
      this.avisar(null, 'Cancelación deshecha: el entrenamiento vuelve a estar activo.');
    });
  }

  protected abrirCorregir(f: FilaPlanilla): void {
    this.formCorregir.reset({ estado: '', motivo: '' });
    this.abrir(() => this.corrigiendo.set(f));
  }

  protected enviarCorreccion(): void {
    const s = this.seleccionada();
    const f = this.corrigiendo();
    if (!s || !f) return;
    if (this.formCorregir.invalid) return this.errorDialogo.set('Elige el nuevo estado y escribe el motivo (mín. 10 caracteres).');
    const url = `${sesionUrl(s.id)}/asistencia/${encodeURIComponent(f.alumno_id)}`;
    this.ejecutar(this.http.patch<FilaPlanilla[]>(url, this.formCorregir.getRawValue()), (p) => {
      this.planilla.set(p);
      this.corrigiendo.set(null);
      this.avisar(null, `Asistencia de ${f.alumno_nombre} corregida.`);
    }, true);
  }

  protected abrirJustificar(f: FilaPlanilla): void {
    this.formJustificar.reset();
    this.abrir(() => this.justificando.set(f));
  }

  protected enviarJustificacion(): void {
    const s = this.seleccionada();
    const f = this.justificando();
    if (!s || !f || this.formJustificar.invalid) return;
    const cuerpo = { alumno_id: f.alumno_id, motivo: this.formJustificar.getRawValue().motivo };
    this.ejecutar(this.http.post<Justificacion>(`${sesionUrl(s.id)}/justificaciones`, cuerpo), () => {
      this.justificando.set(null);
      this.recargarPlanilla();
      this.cargarJustificaciones();
      this.avisar(null, 'Justificación enviada. El club la revisará.');
    }, true);
  }

  protected abrirRechazo(j: Justificacion): void {
    this.formRechazar.reset();
    this.abrir(() => this.rechazando.set(j));
  }

  protected aprobar(j: Justificacion): void {
    this.revisar(j, { aprobar: true }, false);
  }

  protected rechazar(): void {
    const j = this.rechazando();
    if (!j || this.formRechazar.invalid) return;
    this.revisar(j, { aprobar: false, comentario: this.formRechazar.getRawValue().comentario }, true);
  }

  private revisar(j: Justificacion, cuerpo: object, enDialogo: boolean): void {
    const aprobada = (cuerpo as { aprobar: boolean }).aprobar;
    this.ejecutar(this.http.post<Justificacion>(`${API}/justificaciones/${encodeURIComponent(j.id)}/revisar`, cuerpo), () => {
      this.justificaciones.update((l) => l.filter((x) => x.id !== j.id));
      this.rechazando.set(null);
      if (this.seleccionadaId() === j.sesion_id) this.recargarPlanilla();
      this.avisar(null, `Justificación de ${j.alumno_nombre} ${aprobada ? 'aprobada' : 'rechazada'}.`);
    }, enDialogo);
  }

  // ---------- Apoyo ----------
  protected diaCorto(iso: string): string {
    return DIAS[diaSemana(desdeIso(iso))] ?? '';
  }

  protected hora(h: string): string {
    return h.slice(0, 5);
  }

  protected etiquetaCancelacion(s: Sesion): string {
    return CANCELACION[s.causa_cancelacion ?? 'manual'] ?? 'cancelada';
  }

  protected pct(n: number): string {
    const total = this.filas().length;
    return total ? `${Math.round((n / total) * 100)}%` : '0%';
  }

  private abrir(mostrar: () => void): void {
    this.errorDialogo.set(null);
    this.mensaje.set(null);
    mostrar();
  }

  /**
   * Ejecuta una acción mostrando el estado ocupado. Si falla, el error se muestra dentro del popup
   * (`enDialogo`) para no perder lo escrito, o arriba de la pantalla.
   */
  private ejecutar<T>(peticion: Observable<T>, ok: (r: T) => void, enDialogo = false): void {
    this.ocupado.set(true);
    this.mensaje.set(null);
    this.errorDialogo.set(null);
    peticion.subscribe({
      next: (r) => {
        this.ocupado.set(false);
        ok(r);
      },
      error: (e) => {
        this.ocupado.set(false);
        if (enDialogo) this.errorDialogo.set(mensajeError(e));
        else this.avisar(e);
      },
    });
  }

  private avisar(e: unknown, texto?: string): void {
    this.mensaje.set(e ? { error: true, texto: mensajeError(e) } : { error: false, texto: texto ?? '' });
  }
}
