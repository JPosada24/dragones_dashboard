import { DatePipe, NgTemplateOutlet } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Observable, map, of, switchMap, tap, throwError } from 'rxjs';

import { Operacion } from '../../compartido/operacion';
import { Aviso } from '../../compartido/aviso';
import { Dialogo } from '../../compartido/dialogo';
import { PESTANAS_ALUMNOS, Pestanas } from '../../compartido/pestanas';
import { mensajeError } from '../../compartido/errores';
import { ESTADO_INSCRIPCION, TIPOS_DOCUMENTO, TipoDocumento } from '../../compartido/estados';
import { isoLocal } from '../../compartido/fechas';
import { PesosPipe } from '../../compartido/pesos.pipe';
import { AuthService } from '../../core/auth/auth.service';
import { AlumnosApi, VinculoNuevo } from './alumnos.api';
import {
  Acudiente, AcudienteVinculado, Alumno, Documento, EstadoCuenta, NOMBRE_NIVEL, Nivel, Rama, RegistroHistorial,
} from './alumnos.modelos';
import { DocumentosAlumno } from './documentos-alumno';
import { FormaPago, inscribirConPago, problemaPago, resumenPago } from '../inscripciones/inscribir';
import { Inscripcion } from '../inscripciones/inscripciones.modelos';

const ESTADO_ASISTENCIA: Record<string, string> = {
  presente: 'Presente',
  ausente: 'Ausente',
  justificado: 'Justificado',
};

/** Máximo que pide la lista; el club es pequeño, para más está la búsqueda. */
const LIMITE_LISTA = 200;

/** Resultado de buscar al acudiente por documento: encontrado, no existe (se crea) o sin buscar aún. */
type BusquedaAcudiente = Acudiente | 'nuevo' | null;

@Component({
  selector: 'app-alumnos',
  imports: [DatePipe, NgTemplateOutlet, ReactiveFormsModule, RouterLink, Aviso, Dialogo, DocumentosAlumno, PesosPipe, Pestanas],
  templateUrl: './alumnos.html',
  styleUrl: './alumnos.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AlumnosPage implements OnInit {
  private readonly http = inject(HttpClient); // solo para inscribirConPago (compartido con Inscripciones)
  private readonly api = inject(AlumnosApi);
  private readonly auth = inject(AuthService);
  private readonly ruta = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly fb = inject(FormBuilder).nonNullable;
  protected readonly pestanas = PESTANAS_ALUMNOS;

  // ---------- Permisos (la autorización real la hace el servidor) ----------
  protected readonly esStaff = computed(() => this.auth.tiene('alumnos.ver_todos'));
  protected readonly veTodasLasRamas = computed(() => this.auth.tiene('alumnos.ver_todos'));
  protected readonly puedeEditar = computed(() => this.auth.tiene('alumnos.editar'));
  protected readonly puedeInscribir = computed(() => this.auth.tiene('inscripciones.crear'));
  protected readonly puedeAbonar = computed(() => this.auth.tiene('inscripciones.abonar'));
  protected readonly puedeEliminar = computed(() => this.auth.tiene('alumnos.eliminar'));
  protected readonly puedeVerDocumento = computed(() => this.auth.tiene('alumnos.ver_documento'));

  protected readonly tiposDocumento = TIPOS_DOCUMENTO;
  protected readonly estadoInscripcion = ESTADO_INSCRIPCION;
  protected readonly estadoAsistencia = ESTADO_ASISTENCIA;
  protected readonly hoy = isoLocal(new Date());
  protected readonly limiteLista = LIMITE_LISTA;

  // ---------- Lista ----------
  protected readonly alumnos = signal<Alumno[] | null>(null);
  protected readonly buscar = signal('');
  protected readonly filtroRama = signal<Rama | ''>('');
  protected readonly filtroNivel = signal<Nivel | ''>('');
  protected readonly nombreNivel = NOMBRE_NIVEL;
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
  /** Inscripción del año en curso (la vigente o la última), para la tarjeta de la ficha. */
  protected readonly inscripcion = signal<Inscripcion | null>(null);
  protected readonly vigente = computed(() => {
    const i = this.inscripcion();
    return !!i && ['pendiente_pago', 'activo', 'a_expulsar'].includes(i.estado);
  });
  protected readonly textoNuevo = computed(() => (this.puedeInscribir() ? 'Inscribir alumno nuevo' : 'Nuevo alumno'));
  protected readonly errorFicha = signal(false);

  protected readonly op = new Operacion();
  protected readonly mensaje = this.op.mensaje;
  protected readonly errorDialogo = this.op.errorDialogo;
  protected readonly ocupado = this.op.ocupado;

  // ---------- Ventanas emergentes ----------
  protected readonly editandoAlumno = signal<'nuevo' | 'editar' | null>(null);
  protected readonly agregandoAcudiente = signal(false);
  protected readonly quitandoAcudiente = signal<AcudienteVinculado | null>(null);
  protected readonly inscribiendo = signal(false);
  protected readonly abonando = signal(false);
  protected readonly registrandoAutorizacion = signal(false);
  protected readonly eliminando = signal(false);
  /** Para confirmar hay que escribir el código del alumno (evita borrar por un clic). */
  protected readonly confirmacion = signal('');
  protected readonly busquedaAcudiente = signal<BusquedaAcudiente>(null);

  protected readonly formAlumno = this.fb.group({
    nombres: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(80)]],
    apellidos: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(80)]],
    tipo_documento: this.fb.control<TipoDocumento | ''>('', Validators.required),
    documento: ['', Validators.maxLength(30)],
    fecha_nacimiento: ['', Validators.required],
    rama: this.fb.control<Rama | ''>('', Validators.required),
    nivel: this.fb.control<Nivel | ''>('', Validators.required),
    telefono: ['', Validators.maxLength(20)],
    email: ['', [Validators.email, Validators.maxLength(254)]],
    direccion: ['', Validators.maxLength(200)],
    eps: ['', Validators.maxLength(80)],
    activo: true,
  });
  protected readonly formAcudiente = this.fb.group({
    tipo_documento: this.fb.control<TipoDocumento | ''>('', Validators.required),
    documento: ['', Validators.maxLength(30)],
    parentesco: ['', Validators.maxLength(30)],
    principal: false,
    nombres: ['', Validators.maxLength(80)],
    apellidos: ['', Validators.maxLength(80)],
    telefono: ['', Validators.maxLength(20)],
    email: ['', [Validators.email, Validators.maxLength(254)]],
  });
  /** Autorización de datos: quién la dio, si permite fotos y la confirmación de que quedó por escrito. */
  protected readonly formAutorizacion = this.fb.group({
    nombre: ['', Validators.maxLength(120)],
    imagen: this.fb.control<'si' | 'no' | ''>(''),
    confirmada: false,
  });
  protected readonly formAbono = this.fb.group({
    monto: this.fb.control<number | null>(null, [Validators.required, Validators.min(1), Validators.max(100_000_000)]),
    fecha_pago: [''], // vacía = hoy
  });
  /** Inscripción del año (al crear el alumno o desde su ficha) y su primer abono. */
  protected readonly formInscripcion = this.fb.group({
    pago: this.fb.control<FormaPago>('ninguno'),
    monto: this.fb.control<number | null>(null, [Validators.min(1), Validators.max(100_000_000)]),
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
    const filtro = {
      limite: LIMITE_LISTA, buscar: this.buscar(), rama: this.filtroRama(), nivel: this.filtroNivel(),
      activo: this.esStaff() ? !this.verInactivos() : undefined,
    };
    this.api.listar(filtro).subscribe({
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

  protected cambiarNivel(nivel: Nivel | ''): void {
    this.filtroNivel.update((actual) => (actual === nivel ? '' : nivel)); // tocar el activo lo quita
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
    this.api.ficha(id, this.hoy.slice(0, 4)).subscribe({
      next: (r) => {
        if (this.seleccionadoId() !== id) return; // el usuario ya eligió otro
        this.alumno.set(r.alumno);
        this.cuenta.set(r.cuenta);
        this.historial.set(r.historial);
        this.documentos.set(r.documentos);
        // La vigente si la hay; si no, la más reciente del año (la lista viene de la más nueva a la más vieja).
        const vigente = r.inscripciones.find((i) => ['pendiente_pago', 'activo', 'a_expulsar'].includes(i.estado));
        this.inscripcion.set(vigente ?? r.inscripciones[0] ?? null);
      },
      error: () => this.errorFicha.set(true),
    });
  }

  protected abrirEliminar(): void {
    this.confirmacion.set('');
    this.op.abrir(() => this.eliminando.set(true));
  }

  protected eliminarAlumno(): void {
    const a = this.alumno();
    if (!a || this.confirmacion().trim().toUpperCase() !== a.codigo) return;
    this.op.ejecutar(this.api.eliminar(a.id), () => {
      this.eliminando.set(false);
      this.alumnos.update((lista) => lista?.filter((x) => x.id !== a.id) ?? lista);
      this.volverALista();
      this.op.exito(`${a.nombres} ${a.apellidos} (${a.codigo}) fue eliminado con toda su información.`);
    });
  }

  protected volverALista(): void {
    this.seleccionadoId.set(null);
    this.alumno.set(null);
    void this.router.navigate([], { queryParams: {}, replaceUrl: true });
  }

  /** Muestra el documento completo (solo Admin/SuperAdmin; el servidor deja registro en la auditoría). */
  protected verDocumento(a: Alumno): void {
    this.op.ejecutar(
      this.api.documentoIdentidad(a.id),
      (r) => this.documentoCompleto.set(r.documento), { enDialogo: false });
  }

  private reemplazar(a: Alumno): void {
    this.alumno.set(a);
    this.alumnos.update((lista) => lista?.map((x) => (x.id === a.id ? a : x)) ?? lista);
  }

  // ---------- Alumno: crear / editar ----------
  protected abrirNuevo(): void {
    this.formAlumno.reset({ rama: '' });
    this.formAutorizacion.reset();
    this.reiniciarAcudiente();
    this.reiniciarInscripcion();
    this.op.abrir(() => this.editandoAlumno.set('nuevo'));
  }

  protected abrirEditar(a: Alumno): void {
    this.formAlumno.reset({
      nombres: a.nombres, apellidos: a.apellidos, tipo_documento: a.tipo_documento, documento: '',
      fecha_nacimiento: a.fecha_nacimiento, rama: a.rama, nivel: a.nivel, telefono: a.telefono ?? '', email: a.email ?? '',
      direccion: a.direccion ?? '', eps: a.eps ?? '', activo: a.activo,
    });
    this.op.abrir(() => this.editandoAlumno.set('editar'));
  }

  protected guardarAlumno(): void {
    const modo = this.editandoAlumno();
    const f = this.formAlumno.getRawValue();
    const { rama, nivel, tipo_documento } = f;
    if (this.formAlumno.invalid || !rama || !nivel || !tipo_documento || (modo === 'nuevo' && !f.documento.trim())) {
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
      rama, nivel, ...opcionales,
    };

    if (modo === 'nuevo') {
      const error = this.problemaAcudiente(false) ?? this.problemaAutorizacion() ?? this.problemaInscripcion();
      if (error) return this.errorDialogo.set(error);
      const ficha = { ...base, tipo_documento, documento: f.documento, autorizacion: this.autorizacion() };
      const pago = this.formInscripcion.getRawValue();
      if (!this.puedeInscribir()) {
        // Sin permiso de inscribir solo se registra la ficha (hoy ningún rol está en ese caso).
        const alta = this.vinculo$().pipe(
          switchMap((v) => this.api.crear({ ...ficha, acudientes: v ? [v] : [] })),
        );
        this.op.ejecutar(alta, (a) => this.terminarAlta(a.id, `${a.nombres} ${a.apellidos} quedó registrado.`));
        return;
      }
      // Ficha + inscripción + primer pago en una sola operación: si algo falla, no queda nada a medias.
      const alta = this.vinculo$().pipe(
        switchMap((v) => this.api.inscribirNuevo({
          alumno: { ...ficha, acudientes: v ? [v] : [] },
          pago: this.puedeAbonar() && pago.pago !== 'ninguno'
            ? { forma: pago.pago, monto: pago.pago === 'parcial' ? pago.monto : null }
            : { forma: 'ninguno' },
        })),
      );
      this.op.ejecutar(alta, (i) => this.terminarAlta(i.alumno_id, `${i.alumno_nombre} quedó inscrito. ${resumenPago(i)}`));
      return;
    }

    const actual = this.alumno();
    if (!actual) return;
    const cambios: Record<string, unknown> = { ...base, activo: f.activo };
    if (f.documento.trim()) Object.assign(cambios, { tipo_documento, documento: f.documento });
    else if (tipo_documento !== actual.tipo_documento) cambios['tipo_documento'] = tipo_documento;
    this.op.ejecutar(this.api.actualizar(actual.id, cambios), (a) => {
      this.editandoAlumno.set(null);
      this.reemplazar(a);
      this.documentoCompleto.set(null);
      this.op.exito('Cambios guardados.');
    });
  }

  // ---------- Autorización de datos (Ley 1581) ----------
  private problemaAutorizacion(): string | null {
    const f = this.formAutorizacion.getRawValue();
    if (f.nombre.trim().length < 3) return 'Escribe quién autorizó el tratamiento de datos.';
    if (!f.imagen) return 'Indica si autorizó publicar fotos del alumno.';
    if (!f.confirmada) return 'Confirma que la autorización quedó firmada o por escrito.';
    return null;
  }

  private autorizacion(): { nombre: string; imagen: boolean } {
    const f = this.formAutorizacion.getRawValue();
    return { nombre: f.nombre.trim(), imagen: f.imagen === 'si' };
  }

  protected abrirAutorizacion(): void {
    this.formAutorizacion.reset();
    this.op.abrir(() => this.registrandoAutorizacion.set(true));
  }

  protected guardarAutorizacion(): void {
    const a = this.alumno();
    if (!a) return;
    const error = this.problemaAutorizacion();
    if (error) return this.errorDialogo.set(error);
    this.op.ejecutar(this.api.registrarAutorizacion(a.id, this.autorizacion()), (r) => {
      this.registrandoAutorizacion.set(false);
      this.reemplazar(r);
      this.op.exito('Autorización de datos registrada.');
    });
  }

  private terminarAlta(alumnoId: string, texto: string): void {
    this.editandoAlumno.set(null);
    this.cargarLista();
    this.seleccionar(alumnoId);
    this.op.exito(texto);
  }

  // ---------- Inscripción del año ----------
  private reiniciarInscripcion(): void {
    this.formInscripcion.reset({ pago: 'ninguno', monto: null });
  }

  protected abrirInscribir(): void {
    this.reiniciarInscripcion();
    this.op.abrir(() => this.inscribiendo.set(true));
  }

  private problemaInscripcion(): string | null {
    const f = this.formInscripcion.getRawValue();
    return this.puedeAbonar() ? problemaPago(f.pago, f.monto) : null;
  }

  private inscribir$(alumnoId: string): Observable<Inscripcion> {
    const f = this.formInscripcion.getRawValue();
    return inscribirConPago(this.http, alumnoId, {
      forma: f.pago, monto: f.monto, hoy: this.hoy, puedeAbonar: this.puedeAbonar(),
    });
  }

  protected pctPagado(i: Inscripcion): string {
    return i.valor ? `${Math.round(((i.monto_pagado ?? 0) / i.valor) * 100)}%` : '100%';
  }

  protected abonable(i: Inscripcion): boolean {
    return this.puedeAbonar() && i.estado === 'pendiente_pago' && i.saldo > 0;
  }

  protected abrirAbono(): void {
    this.formAbono.reset({ monto: null, fecha_pago: '' });
    this.op.abrir(() => this.abonando.set(true));
  }

  protected guardarAbono(): void {
    const i = this.inscripcion();
    if (!i) return;
    if (this.formAbono.invalid) return this.errorDialogo.set('Revisa el valor y la fecha del abono.');
    const { monto, fecha_pago } = this.formAbono.getRawValue();
    if (monto === null) return;
    this.op.ejecutar(this.api.abonar(i.id, { monto, fecha_pago: fecha_pago || this.hoy }), (r) => {
      this.abonando.set(false);
      this.seleccionar(r.alumno_id); // refresca estado de cuenta y punto de la lista
      this.cargarLista();
      this.op.exito(`Abono registrado. ${resumenPago(r)}`);
    });
  }

  protected guardarInscripcion(): void {
    const a = this.alumno();
    if (!a) return;
    const error = this.problemaInscripcion();
    if (error) return this.errorDialogo.set(error);
    this.op.ejecutar(this.inscribir$(a.id), (i) => {
      this.inscribiendo.set(false);
      this.seleccionar(a.id);
      this.cargarLista();
      this.op.exito(`Inscripción registrada. ${resumenPago(i)}`);
    });
  }

  // ---------- Acudientes ----------
  private reiniciarAcudiente(): void {
    this.formAcudiente.reset();
    this.busquedaAcudiente.set(null);
  }

  protected abrirAgregarAcudiente(): void {
    this.reiniciarAcudiente();
    this.op.abrir(() => this.agregandoAcudiente.set(true));
  }

  /** Busca por documento completo: así se reutiliza el acudiente de un hermano sin duplicarlo. */
  protected buscarAcudiente(): void {
    const { tipo_documento, documento } = this.formAcudiente.getRawValue();
    if (!documento.trim()) return this.errorDialogo.set('Escribe el número de documento del acudiente.');
    this.errorDialogo.set(null);
    this.api.buscarAcudiente(tipo_documento, documento).subscribe({
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
    const tipo = f.tipo_documento;
    if (!tipo) return throwError(() => new Error('Elige el tipo de documento del acudiente.'));
    const vinculo = (id: string): VinculoNuevo => ({ acudiente_id: id, parentesco: f.parentesco, principal: f.principal });
    if (b !== 'nuevo') return of(vinculo(b.id));
    return this.api
      .crearAcudiente({
        nombres: f.nombres, apellidos: f.apellidos, tipo_documento: tipo, documento: f.documento,
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
      // problemaAcudiente(true) ya exige el documento, así que aquí siempre hay vínculo.
      switchMap((v) => (v ? this.api.vincularAcudiente(a.id, v) : throwError(() => new Error('Falta el acudiente.')))),
    );
    this.op.ejecutar(peticion, (r) => {
      this.agregandoAcudiente.set(false);
      this.reemplazar(r);
      this.op.exito('Acudiente vinculado.');
    });
  }

  protected abrirQuitarAcudiente(v: AcudienteVinculado): void {
    this.op.abrir(() => this.quitandoAcudiente.set(v));
  }

  protected quitarAcudiente(): void {
    const a = this.alumno();
    const v = this.quitandoAcudiente();
    if (!a || !v) return;
    this.op.ejecutar(this.api.desvincularAcudiente(a.id, v.acudiente_id), (r) => {
      this.quitandoAcudiente.set(null);
      this.reemplazar(r);
      this.op.exito('Acudiente desvinculado.');
    });
  }

  // ---------- Utilidades ----------


}
