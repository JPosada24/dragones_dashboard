import { DatePipe, NgTemplateOutlet } from '@angular/common';
import { HttpClient, HttpParams } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { Observable, forkJoin, map, of, switchMap, tap } from 'rxjs';

import { Aviso } from '../../compartido/aviso';
import { Dialogo } from '../../compartido/dialogo';
import { mensajeError } from '../../compartido/errores';
import { ESTADO_INSCRIPCION, TIPOS_DOCUMENTO } from '../../compartido/estados';
import { isoLocal } from '../../compartido/fechas';
import { PesosPipe } from '../../compartido/pesos.pipe';
import { AuthService } from '../../core/auth/auth.service';
import { API } from '../../core/modelos';
import {
  Acudiente, AcudienteVinculado, Alumno, Documento, EstadoCuenta, InscripcionBasica, Rama, RegistroHistorial,
} from './alumnos.modelos';

const TIPOS_ARCHIVO: { valor: string; texto: string }[] = [
  { valor: 'identidad', texto: 'Documento de identidad' },
  { valor: 'eps', texto: 'Certificado de EPS' },
  { valor: 'consentimiento', texto: 'Consentimiento informado' },
  { valor: 'certificado_medico', texto: 'Certificado médico' },
  { valor: 'foto', texto: 'Foto' },
  { valor: 'otro', texto: 'Otro' },
];

const ESTADO_ASISTENCIA: Record<string, string> = {
  presente: 'Presente',
  ausente: 'Ausente',
  justificado: 'Justificado',
};

/** Máximo que pide la lista; el club es pequeño, para más está la búsqueda. */
const LIMITE_LISTA = 200;

const alumnoUrl = (id: string) => `${API}/alumnos/${encodeURIComponent(id)}`;

interface VinculoNuevo {
  acudiente_id: string;
  parentesco: string;
  principal: boolean;
}

type FormaPago = 'ninguno' | 'parcial' | 'completo';

/** Resultado de buscar al acudiente por documento: encontrado, no existe (se crea) o sin buscar aún. */
type BusquedaAcudiente = Acudiente | 'nuevo' | null;

@Component({
  selector: 'app-alumnos',
  imports: [DatePipe, NgTemplateOutlet, ReactiveFormsModule, Aviso, Dialogo, PesosPipe],
  templateUrl: './alumnos.html',
  styleUrl: './alumnos.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AlumnosPage implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private readonly ruta = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly pesos = new PesosPipe();

  // ---------- Permisos (la autorización real la hace el servidor) ----------
  protected readonly esStaff = computed(() => this.auth.tieneAlguno(['alumnos.ver_todos', 'alumnos.ver_rama']));
  protected readonly veTodasLasRamas = computed(() => this.auth.tiene('alumnos.ver_todos'));
  protected readonly puedeEditar = computed(() => this.auth.tiene('alumnos.editar'));
  protected readonly puedeInscribir = computed(() => this.auth.tiene('inscripciones.crear'));
  protected readonly puedeAbonar = computed(() => this.auth.tiene('inscripciones.abonar'));
  /** Rama fija para quien solo maneja la suya (el Entrenador). */
  protected readonly ramaPropia = computed(() => (this.veTodasLasRamas() ? null : (this.auth.usuario()?.rama ?? null)));

  protected readonly tiposDocumento = TIPOS_DOCUMENTO;
  protected readonly tiposArchivo = TIPOS_ARCHIVO;
  protected readonly estadoInscripcion = ESTADO_INSCRIPCION;
  protected readonly estadoAsistencia = ESTADO_ASISTENCIA;
  protected readonly hoy = isoLocal(new Date());
  protected readonly limiteLista = LIMITE_LISTA;

  // ---------- Lista ----------
  protected readonly alumnos = signal<Alumno[] | null>(null);
  protected readonly buscar = signal('');
  protected readonly filtroRama = signal<Rama | ''>('');
  protected readonly verInactivos = signal(false);
  protected readonly errorLista = signal(false);
  private temporizador: ReturnType<typeof setTimeout> | undefined;

  // ---------- Ficha ----------
  protected readonly seleccionadoId = signal<string | null>(null);
  protected readonly alumno = signal<Alumno | null>(null);
  protected readonly cuenta = signal<EstadoCuenta | null>(null);
  protected readonly historial = signal<RegistroHistorial[]>([]);
  protected readonly documentos = signal<Documento[]>([]);
  protected readonly documentoCompleto = signal<string | null>(null);
  protected readonly errorFicha = signal(false);

  protected readonly mensaje = signal<{ error: boolean; texto: string } | null>(null);
  protected readonly errorDialogo = signal<string | null>(null);
  protected readonly ocupado = signal(false);

  // ---------- Ventanas emergentes ----------
  protected readonly editandoAlumno = signal<'nuevo' | 'editar' | null>(null);
  protected readonly agregandoAcudiente = signal(false);
  protected readonly quitandoAcudiente = signal<AcudienteVinculado | null>(null);
  protected readonly subiendoDocumento = signal(false);
  protected readonly eliminandoDocumento = signal<Documento | null>(null);
  protected readonly inscribiendo = signal(false);
  protected readonly busquedaAcudiente = signal<BusquedaAcudiente>(null);
  protected readonly archivo = signal<File | null>(null);

  protected readonly formAlumno = this.fb.group({
    nombres: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(80)]],
    apellidos: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(80)]],
    tipo_documento: ['TI', Validators.required],
    documento: ['', Validators.maxLength(30)],
    fecha_nacimiento: ['', Validators.required],
    rama: this.fb.control<Rama>('femenina', Validators.required),
    telefono: ['', Validators.maxLength(20)],
    email: ['', [Validators.email, Validators.maxLength(254)]],
    direccion: ['', Validators.maxLength(200)],
    eps: ['', Validators.maxLength(80)],
    activo: true,
  });
  protected readonly formAcudiente = this.fb.group({
    tipo_documento: ['CC', Validators.required],
    documento: ['', Validators.maxLength(30)],
    parentesco: ['', Validators.maxLength(30)],
    principal: false,
    nombres: ['', Validators.maxLength(80)],
    apellidos: ['', Validators.maxLength(80)],
    telefono: ['', Validators.maxLength(20)],
    email: ['', [Validators.email, Validators.maxLength(254)]],
  });
  protected readonly formDocumento = this.fb.group({ tipo: ['identidad', Validators.required] });
  /** Inscripción del año (al crear el alumno o desde su ficha) y su primer abono. */
  protected readonly formInscripcion = this.fb.group({
    inscribir: true,
    pago: this.fb.control<FormaPago>('ninguno'),
    monto: [0, [Validators.min(1), Validators.max(100_000_000)]],
  });

  // ---------- Derivados ----------
  protected readonly asistenciaResumen = computed(() => {
    const h = this.historial();
    const asistio = h.filter((r) => r.estado !== 'ausente').length;
    return { asistio, total: h.length };
  });

  constructor() {
    inject(DestroyRef).onDestroy(() => clearTimeout(this.temporizador));
  }

  ngOnInit(): void {
    this.cargarLista();
    const id = this.ruta.snapshot.queryParamMap.get('id');
    if (id) this.seleccionar(id);
  }

  // ---------- Lista ----------
  protected cargarLista(): void {
    let params = new HttpParams().set('limit', LIMITE_LISTA);
    const texto = this.buscar().trim();
    if (texto.length >= 2) params = params.set('buscar', texto);
    if (this.filtroRama()) params = params.set('rama', this.filtroRama());
    if (this.esStaff()) params = params.set('activo', !this.verInactivos());
    this.http.get<Alumno[]>(`${API}/alumnos`, { params }).subscribe({
      next: (lista) => {
        this.errorLista.set(false);
        this.alumnos.set(lista);
        // La familia con un solo alumno lo ve directo.
        const [unico] = lista;
        if (!this.esStaff() && unico && lista.length === 1 && !this.seleccionadoId()) this.seleccionar(unico.id);
      },
      error: () => this.errorLista.set(true),
    });
  }

  protected escribirBusqueda(texto: string): void {
    this.buscar.set(texto);
    clearTimeout(this.temporizador);
    this.temporizador = setTimeout(() => this.cargarLista(), 300);
  }

  protected cambiarRama(rama: Rama | ''): void {
    this.filtroRama.set(rama);
    this.cargarLista();
  }

  protected alternarInactivos(): void {
    this.verInactivos.update((v) => !v);
    this.cargarLista();
  }

  protected iniciales(a: { nombres: string; apellidos: string }): string {
    return `${a.nombres.charAt(0)}${a.apellidos.charAt(0)}`.toUpperCase();
  }

  /** Color del punto de la lista según la inscripción del año. */
  protected tono(a: Alumno): string {
    if (!a.activo) return 'apagado';
    switch (a.inscripcion_estado) {
      case 'activo':
        return 'ok';
      case 'pendiente_pago':
        return 'pendiente';
      case 'a_expulsar':
      case 'expulsado':
      case 'rechazado':
        return 'mal';
      default:
        return 'apagado';
    }
  }

  // ---------- Ficha ----------
  protected seleccionar(id: string): void {
    this.seleccionadoId.set(id);
    this.documentoCompleto.set(null);
    this.errorFicha.set(false);
    this.alumno.set(null);
    void this.router.navigate([], { queryParams: { id }, replaceUrl: true });
    forkJoin({
      alumno: this.http.get<Alumno>(alumnoUrl(id)),
      cuenta: this.http.get<EstadoCuenta>(`${alumnoUrl(id)}/estado-cuenta`),
      historial: this.http.get<RegistroHistorial[]>(`${alumnoUrl(id)}/asistencia`),
      documentos: this.http.get<Documento[]>(`${alumnoUrl(id)}/documentos`),
    }).subscribe({
      next: (r) => {
        if (this.seleccionadoId() !== id) return; // el usuario ya eligió otro
        this.alumno.set(r.alumno);
        this.cuenta.set(r.cuenta);
        this.historial.set(r.historial);
        this.documentos.set(r.documentos);
      },
      error: () => this.errorFicha.set(true),
    });
  }

  protected volverALista(): void {
    this.seleccionadoId.set(null);
    this.alumno.set(null);
    void this.router.navigate([], { queryParams: {}, replaceUrl: true });
  }

  /** Muestra el documento completo (solo Admin/SuperAdmin; el servidor deja registro en la auditoría). */
  protected verDocumento(a: Alumno): void {
    this.ejecutar(
      this.http.get<{ documento: string }>(`${alumnoUrl(a.id)}/documento-identidad`),
      (r) => this.documentoCompleto.set(r.documento),
    );
  }

  private reemplazar(a: Alumno): void {
    this.alumno.set(a);
    this.alumnos.update((lista) => lista?.map((x) => (x.id === a.id ? a : x)) ?? lista);
  }

  // ---------- Alumno: crear / editar ----------
  protected abrirNuevo(): void {
    this.formAlumno.reset({ rama: this.ramaPropia() === 'masculina' ? 'masculina' : 'femenina' });
    this.reiniciarAcudiente();
    this.reiniciarInscripcion();
    this.abrir(() => this.editandoAlumno.set('nuevo'));
  }

  protected abrirEditar(a: Alumno): void {
    this.formAlumno.reset({
      nombres: a.nombres, apellidos: a.apellidos, tipo_documento: a.tipo_documento, documento: '',
      fecha_nacimiento: a.fecha_nacimiento, rama: a.rama, telefono: a.telefono ?? '', email: a.email ?? '',
      direccion: a.direccion ?? '', eps: a.eps ?? '', activo: a.activo,
    });
    this.abrir(() => this.editandoAlumno.set('editar'));
  }

  protected guardarAlumno(): void {
    const modo = this.editandoAlumno();
    const f = this.formAlumno.getRawValue();
    if (this.formAlumno.invalid || (modo === 'nuevo' && !f.documento.trim())) {
      this.formAlumno.markAllAsTouched();
      this.errorDialogo.set('Revisa los campos obligatorios.');
      return;
    }
    const opcionales = {
      telefono: f.telefono.trim() || null, email: f.email.trim() || null,
      direccion: f.direccion.trim() || null, eps: f.eps.trim() || null,
    };
    const base = {
      nombres: f.nombres, apellidos: f.apellidos, fecha_nacimiento: f.fecha_nacimiento,
      rama: this.ramaPropia() ?? f.rama, ...opcionales,
    };

    if (modo === 'nuevo') {
      const error = this.problemaAcudiente(false);
      if (error) return this.errorDialogo.set(error);
      const peticion = this.vinculo$().pipe(
        switchMap((v) =>
          this.http.post<Alumno>(`${API}/alumnos`, {
            ...base, tipo_documento: f.tipo_documento, documento: f.documento, acudientes: v ? [v] : [],
          }),
        ),
      );
      const errorPago = this.problemaInscripcion();
      if (errorPago) return this.errorDialogo.set(errorPago);
      const inscribir = this.puedeInscribir() && this.formInscripcion.getRawValue().inscribir;
      this.ejecutar(peticion, (a) => {
        const nombre = `${a.nombres} ${a.apellidos}`;
        const terminar = (texto: string, error = false) => {
          this.editandoAlumno.set(null);
          this.cargarLista();
          this.seleccionar(a.id);
          this.mensaje.set({ error, texto });
        };
        if (!inscribir) return terminar(`${nombre} quedó registrado.`);
        // El alumno ya existe: si la inscripción falla, se cierra el popup (reintentar lo duplicaría) y se avisa.
        this.ocupado.set(true);
        this.inscribir$(a.id).subscribe({
          next: (i) => {
            this.ocupado.set(false);
            terminar(`${nombre} quedó registrado e inscrito. ${this.textoInscripcion(i)}`);
          },
          error: (e) => {
            this.ocupado.set(false);
            const detalle = `${nombre} quedó registrado, pero falló la inscripción: ${mensajeError(e)}`;
            terminar(`${detalle} Puedes inscribirlo desde su ficha.`, true);
          },
        });
      }, true);
      return;
    }

    const actual = this.alumno();
    if (!actual) return;
    const cambios: Record<string, unknown> = { ...base, activo: f.activo };
    if (f.documento.trim()) Object.assign(cambios, { tipo_documento: f.tipo_documento, documento: f.documento });
    else if (f.tipo_documento !== actual.tipo_documento) cambios['tipo_documento'] = f.tipo_documento;
    this.ejecutar(this.http.patch<Alumno>(alumnoUrl(actual.id), cambios), (a) => {
      this.editandoAlumno.set(null);
      this.reemplazar(a);
      this.documentoCompleto.set(null);
      this.avisar(null, 'Cambios guardados.');
    }, true);
  }

  // ---------- Inscripción del año ----------
  private reiniciarInscripcion(): void {
    this.formInscripcion.reset({ inscribir: true, pago: 'ninguno', monto: 0 });
  }

  protected abrirInscribir(): void {
    this.reiniciarInscripcion();
    this.abrir(() => this.inscribiendo.set(true));
  }

  /** Qué falta en la forma de pago; null si está bien. */
  private problemaInscripcion(): string | null {
    const f = this.formInscripcion.getRawValue();
    if (!f.inscribir || f.pago !== 'parcial') return null;
    if (!Number.isInteger(f.monto) || f.monto < 1) return 'Escribe el valor del abono (en pesos, sin puntos).';
    return null;
  }

  /** Inscribe al alumno en el año y, si se indicó, registra el primer abono con fecha de hoy. */
  private inscribir$(alumnoId: string): Observable<InscripcionBasica> {
    const f = this.formInscripcion.getRawValue();
    return this.http.post<InscripcionBasica>(`${API}/inscripciones`, { alumno_id: alumnoId }).pipe(
      switchMap((i) => {
        const monto = f.pago === 'completo' ? i.saldo : f.pago === 'parcial' ? f.monto : 0;
        if (!this.puedeAbonar() || monto <= 0 || i.saldo === 0) return of(i);
        const url = `${API}/inscripciones/${encodeURIComponent(i.id)}/pagos`;
        return this.http.post<InscripcionBasica>(url, { fecha_pago: this.hoy, monto });
      }),
    );
  }

  private textoInscripcion(i: InscripcionBasica): string {
    if (i.saldo === 0) return 'La inscripción quedó paga y activa.';
    const pagado = i.monto_pagado ? `Abonó ${this.pesos.transform(i.monto_pagado)}; ` : '';
    return `${pagado}saldo ${this.pesos.transform(i.saldo)} hasta el ${this.fecha(i.fecha_limite_pago)}.`;
  }

  private fecha(iso: string): string {
    const [a, m, d] = iso.split('-');
    return `${d}/${m}/${a}`;
  }

  protected guardarInscripcion(): void {
    const a = this.alumno();
    if (!a) return;
    const error = this.problemaInscripcion();
    if (error) return this.errorDialogo.set(error);
    this.ejecutar(this.inscribir$(a.id), (i) => {
      this.inscribiendo.set(false);
      this.seleccionar(a.id);
      this.cargarLista();
      this.avisar(null, `Inscripción registrada. ${this.textoInscripcion(i)}`);
    }, true);
  }

  // ---------- Acudientes ----------
  private reiniciarAcudiente(): void {
    this.formAcudiente.reset();
    this.busquedaAcudiente.set(null);
  }

  protected abrirAgregarAcudiente(): void {
    this.reiniciarAcudiente();
    this.abrir(() => this.agregandoAcudiente.set(true));
  }

  /** Busca por documento completo: así se reutiliza el acudiente de un hermano sin duplicarlo. */
  protected buscarAcudiente(): void {
    const { tipo_documento, documento } = this.formAcudiente.getRawValue();
    if (!documento.trim()) return this.errorDialogo.set('Escribe el número de documento del acudiente.');
    const params = new HttpParams().set('tipo_documento', tipo_documento).set('documento', documento);
    this.errorDialogo.set(null);
    this.http.get<Acudiente[]>(`${API}/acudientes`, { params }).subscribe({
      next: (r) => this.busquedaAcudiente.set(r[0] ?? 'nuevo'),
      error: (e) => this.errorDialogo.set(mensajeError(e)),
    });
  }

  /** Cambiar el documento obliga a buscar de nuevo. */
  protected documentoAcudienteCambio(): void {
    if (this.busquedaAcudiente() !== null) this.busquedaAcudiente.set(null);
  }

  protected esAcudienteNuevo(b: BusquedaAcudiente): boolean {
    return b === 'nuevo';
  }

  protected acudienteEncontrado(b: BusquedaAcudiente): Acudiente | null {
    return b && b !== 'nuevo' ? b : null;
  }

  /** Qué falta para vincular el acudiente; null si está completo (u opcional y vacío). */
  private problemaAcudiente(obligatorio: boolean): string | null {
    const f = this.formAcudiente.getRawValue();
    if (!f.documento.trim()) return obligatorio ? 'Escribe el documento del acudiente y búscalo.' : null;
    const b = this.busquedaAcudiente();
    if (b === null) return 'Presiona "Buscar" para ver si el acudiente ya está registrado.';
    if (f.parentesco.trim().length < 2) return 'Indica el parentesco (madre, padre, tío…).';
    if (b === 'nuevo' && (f.nombres.trim().length < 2 || f.apellidos.trim().length < 2 || !f.telefono.trim())) {
      return 'Completa nombres, apellidos y teléfono del acudiente nuevo.';
    }
    if (this.formAcudiente.invalid) return 'Revisa los datos del acudiente.';
    return null;
  }

  /** El vínculo a enviar; si el acudiente no existe, primero lo registra. */
  private vinculo$(): Observable<VinculoNuevo | null> {
    const f = this.formAcudiente.getRawValue();
    const b = this.busquedaAcudiente();
    if (!f.documento.trim() || b === null) return of(null);
    const vinculo = (id: string): VinculoNuevo => ({ acudiente_id: id, parentesco: f.parentesco, principal: f.principal });
    if (b !== 'nuevo') return of(vinculo(b.id));
    return this.http
      .post<Acudiente>(`${API}/acudientes`, {
        nombres: f.nombres, apellidos: f.apellidos, tipo_documento: f.tipo_documento, documento: f.documento,
        telefono: f.telefono, email: f.email.trim() || null,
      })
      .pipe(
        tap((a) => this.busquedaAcudiente.set(a)), // si lo siguiente falla, el reintento no lo duplica
        map((a) => vinculo(a.id)),
      );
  }

  protected vincularAcudiente(): void {
    const a = this.alumno();
    if (!a) return;
    const error = this.problemaAcudiente(true);
    if (error) return this.errorDialogo.set(error);
    const peticion = this.vinculo$().pipe(
      switchMap((v) => this.http.post<Alumno>(`${alumnoUrl(a.id)}/acudientes`, v)),
    );
    this.ejecutar(peticion, (r) => {
      this.agregandoAcudiente.set(false);
      this.reemplazar(r);
      this.avisar(null, 'Acudiente vinculado.');
    }, true);
  }

  protected abrirQuitarAcudiente(v: AcudienteVinculado): void {
    this.abrir(() => this.quitandoAcudiente.set(v));
  }

  protected quitarAcudiente(): void {
    const a = this.alumno();
    const v = this.quitandoAcudiente();
    if (!a || !v) return;
    const url = `${alumnoUrl(a.id)}/acudientes/${encodeURIComponent(v.acudiente_id)}`;
    this.ejecutar(this.http.delete<Alumno>(url), (r) => {
      this.quitandoAcudiente.set(null);
      this.reemplazar(r);
      this.avisar(null, 'Acudiente desvinculado.');
    }, true);
  }

  // ---------- Documentos ----------
  protected textoArchivo(tipo: string): string {
    return TIPOS_ARCHIVO.find((t) => t.valor === tipo)?.texto ?? tipo;
  }

  protected tamano(bytes: number): string {
    return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }

  protected abrirSubir(): void {
    this.formDocumento.reset();
    this.archivo.set(null);
    this.abrir(() => this.subiendoDocumento.set(true));
  }

  protected elegirArchivo(evento: Event): void {
    this.archivo.set((evento.target as HTMLInputElement).files?.[0] ?? null);
  }

  protected subirDocumento(): void {
    const a = this.alumno();
    const archivo = this.archivo();
    if (!a) return;
    if (!archivo) return this.errorDialogo.set('Elige el archivo (PDF, JPG o PNG).');
    const datos = new FormData();
    datos.append('tipo', this.formDocumento.getRawValue().tipo);
    datos.append('archivo', archivo);
    this.ejecutar(this.http.post<Documento>(`${alumnoUrl(a.id)}/documentos`, datos), (d) => {
      this.subiendoDocumento.set(false);
      this.documentos.update((lista) => [d, ...lista]);
      this.avisar(null, 'Documento subido.');
    }, true);
  }

  /** Descarga con el token (no es un enlace público) y la guarda con su nombre original. */
  protected descargar(d: Documento): void {
    const a = this.alumno();
    if (!a) return;
    const url = `${alumnoUrl(a.id)}/documentos/${encodeURIComponent(d.id)}/archivo`;
    this.ejecutar(this.http.get(url, { responseType: 'blob' }), (blob) => {
      const enlace = document.createElement('a');
      enlace.href = URL.createObjectURL(blob);
      enlace.download = d.nombre_original;
      enlace.click();
      setTimeout(() => URL.revokeObjectURL(enlace.href), 1000);
    });
  }

  protected abrirEliminarDocumento(d: Documento): void {
    this.abrir(() => this.eliminandoDocumento.set(d));
  }

  protected eliminarDocumento(): void {
    const a = this.alumno();
    const d = this.eliminandoDocumento();
    if (!a || !d) return;
    const url = `${alumnoUrl(a.id)}/documentos/${encodeURIComponent(d.id)}`;
    this.ejecutar(this.http.delete(url), () => {
      this.eliminandoDocumento.set(null);
      this.documentos.update((lista) => lista.filter((x) => x.id !== d.id));
      this.avisar(null, 'Documento eliminado.');
    }, true);
  }

  // ---------- Utilidades ----------
  private abrir(mostrar: () => void): void {
    this.errorDialogo.set(null);
    this.mensaje.set(null);
    mostrar();
  }

  /** Igual que en Asistencia: el error va dentro del popup (`enDialogo`) para no perder lo escrito. */
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
