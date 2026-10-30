import { HttpErrorResponse, provideHttpClient } from '@angular/common/http';
import { HttpTestingController, TestRequest, provideHttpClientTesting } from '@angular/common/http/testing';
import { registerLocaleData } from '@angular/common';
import localeEsCo from '@angular/common/locales/es-CO';
import { LOCALE_ID } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { mensajeError } from '../../compartido/errores';
import { isoLocal, lunesDe, sumarDias } from '../../compartido/fechas';
import { AuthService } from '../../core/auth/auth.service';
import { API, Usuario } from '../../core/modelos';
import { AsistenciaPage } from './asistencia';
import { FilaPlanilla, Horario, Justificacion, Sesion } from './asistencia.modelos';

registerLocaleData(localeEsCo);

const HOY = isoLocal(new Date());
const STAFF = [
  'alumnos.ver_todos', 'asistencia.marcar_grupo', 'asistencia.corregir', 'justificaciones.revisar', 'sesiones.gestionar',
];
const FAMILIA = ['alumnos.ver_propios', 'asistencia.marcar_propia'];
const HORARIO: Horario = {
  dias: [
    { dia_semana: 0, hora_inicio: '18:00:00', hora_fin: '20:00:00', lugar: null },
    { dia_semana: 2, hora_inicio: '18:00:00', hora_fin: '20:00:00', lugar: 'Coliseo' },
    { dia_semana: 5, hora_inicio: '16:00:00', hora_fin: '18:00:00', lugar: null },
  ],
  dias_anticipacion: 60,
};

const sesion = (extra: Partial<Sesion> = {}): Sesion => ({
  id: 's1', fecha: HOY, hora_inicio: '18:00:00', hora_fin: '20:00:00', lugar: 'Cancha 2', automatica: true,
  cancelada: false, causa_cancelacion: null, motivo_cancelacion: null, cerrada: false, ...extra,
});

const fila = (id: string, nombre: string, extra: Partial<FilaPlanilla> = {}): FilaPlanilla => ({
  alumno_id: id, alumno_nombre: nombre, rama: 'femenina', asistencia: null, justificacion: null, multa: null, ...extra,
});

const JUSTIFICACION: Justificacion = {
  id: 'j1', sesion_id: 's0', fecha_sesion: HOY, rama: 'femenina', alumno_id: 'a9', alumno_nombre: 'Sara Gómez',
  motivo: 'Cita médica programada', estado: 'pendiente', comentario: null, creado_en: HOY, revisada_en: null,
};

describe('AsistenciaPage', () => {
  let backend: HttpTestingController;
  let fixture: ComponentFixture<AsistenciaPage>;

  function crear(permisos: string[]) {
    TestBed.configureTestingModule({
      imports: [AsistenciaPage],
      providers: [provideHttpClient(), provideHttpClientTesting(), { provide: LOCALE_ID, useValue: 'es-CO' }],
    });
    const usuario: Usuario = { id: 'u', email: 'x@club.com', nombre: 'X', rol: 'ADMIN', activo: true, rama: null, permisos };
    TestBed.inject(AuthService).usuario.set(usuario);
    backend = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(AsistenciaPage);
    fixture.detectChanges();
  }

  const el = () => fixture.nativeElement as HTMLElement;
  const texto = () => el().textContent ?? '';
  const boton = (t: string, dentro: ParentNode = el()) =>
    [...dentro.querySelectorAll('button')].find((b) => b.textContent?.trim() === t) as HTMLButtonElement | undefined;
  const dialogo = () => el().querySelector('dialog');
  const pedirSesiones = (): TestRequest => backend.expectOne((r) => r.url === `${API}/sesiones`);
  async function estable() {
    await fixture.whenStable();
    fixture.detectChanges();
  }
  function escribir(selector: string, valor: string) {
    const campo = el().querySelector<HTMLInputElement | HTMLTextAreaElement>(selector)!;
    campo.value = valor;
    campo.dispatchEvent(new Event('input'));
  }

  /** Responde la carga inicial del staff (sesiones, horario, pendientes y alertas) y la planilla. */
  async function cargarStaff(sesiones: Sesion[], planilla: FilaPlanilla[] | null, justificaciones: Justificacion[] = []) {
    crear(STAFF);
    pedirSesiones().flush(sesiones);
    backend.expectOne(`${API}/sesiones/horario`).flush(HORARIO);
    backend.expectOne((r) => r.url === `${API}/justificaciones`).flush(justificaciones);
    backend.expectOne(`${API}/sesiones/alertas`).flush([]);
    if (planilla) backend.expectOne(`${API}/sesiones/s1/asistencia`).flush(planilla);
    await estable();
  }

  afterEach(() => backend.verify());

  it('pide la semana actual y el staff marca y guarda la planilla general', async () => {
    crear(STAFF);
    const req = pedirSesiones();
    expect(req.request.params.get('desde')).toBe(isoLocal(lunesDe(new Date())));
    expect(req.request.params.get('hasta')).toBe(isoLocal(sumarDias(lunesDe(new Date()), 6)));
    expect(req.request.params.has('rama')).toBe(false); // el entrenamiento es general
    req.flush([sesion()]);
    backend.expectOne(`${API}/sesiones/horario`).flush(HORARIO);
    backend.expectOne((r) => r.url === `${API}/justificaciones`).flush([]);
    backend.expectOne(`${API}/sesiones/alertas`).flush([{ alumno_id: 'a3', alumno_nombre: 'Kevin Ruiz', rama: 'masculina', inasistencias_seguidas: 3 }]);
    backend.expectOne(`${API}/sesiones/s1/asistencia`).flush([fila('a1', 'Laura Pérez'), fila('a2', 'Juan Díaz', { rama: 'masculina' })]);
    await estable();

    expect(texto()).toContain('Laura Pérez');
    expect(texto()).toContain('Juan Díaz');
    expect(texto()).toContain('3 seguidas');
    expect(texto()).toContain('Miércoles'); // horario semanal
    expect(boton('Guardar planilla')?.disabled).toBe(true);

    boton('Todos presentes')!.click();
    el().querySelector<HTMLButtonElement>('[aria-label="Ausente: Juan Díaz"]')!.click();
    await estable();
    boton('Guardar planilla')!.click();
    const guardar = backend.expectOne(`${API}/sesiones/s1/asistencia`);
    expect(guardar.request.method).toBe('POST');
    expect(guardar.request.body).toEqual({
      marcas: [{ alumno_id: 'a1', estado: 'presente' }, { alumno_id: 'a2', estado: 'ausente' }],
    });
    guardar.flush([fila('a1', 'Laura Pérez', { asistencia: 'presente' }), fila('a2', 'Juan Díaz', { rama: 'masculina', asistencia: 'ausente' })]);
    await estable();
    expect(texto()).toContain('Planilla guardada (2 marcas)');
  });

  it('filtra la planilla por rama', async () => {
    await cargarStaff([sesion()], [fila('a1', 'Laura Pérez'), fila('a2', 'Juan Díaz', { rama: 'masculina' })]);
    boton('Masculina')!.click();
    await estable();
    expect(texto()).toContain('Juan Díaz');
    expect(texto()).not.toContain('Laura Pérez');
  });

  it('una sesión futura no deja marcar y una cancelada muestra el motivo sin pedir la planilla', async () => {
    await cargarStaff([sesion({ fecha: isoLocal(sumarDias(new Date(), 1)) })], [fila('a1', 'Laura Pérez')]);
    expect(el().querySelector('.marca')).toBeNull();
    expect(boton('Guardar planilla')).toBeUndefined();
    TestBed.resetTestingModule();

    await cargarStaff([sesion({ cancelada: true, causa_cancelacion: 'festivo', motivo_cancelacion: 'Festivo: San José' })], null);
    expect(texto()).toContain('Festivo: San José');
    expect(el().querySelector('.sesion-chip')?.textContent).toContain('festivo');
  });

  it('deshace una cancelación hecha por error', async () => {
    await cargarStaff([sesion({ cancelada: true, causa_cancelacion: 'manual', motivo_cancelacion: 'Por error' })], null);
    boton('undo Deshacer cancelación')!.click();
    backend.expectOne(`${API}/sesiones/s1/reactivar`).flush(sesion());
    backend.expectOne(`${API}/sesiones/s1/asistencia`).flush([fila('a1', 'Laura Pérez')]);
    await estable();
    expect(texto()).toContain('Cancelación deshecha');
    expect(texto()).toContain('Laura Pérez');
    expect(el().querySelector('.marca')).not.toBeNull();
  });

  it('no ofrece deshacer las canceladas por torneo', async () => {
    await cargarStaff([sesion({ cancelada: true, causa_cancelacion: 'torneo', motivo_cancelacion: 'Torneo: Copa' })], null);
    expect(texto()).not.toContain('Deshacer cancelación');
  });

  it('el horario se edita en un popup y se envía completo', async () => {
    await cargarStaff([], null);
    expect(dialogo()).toBeNull();
    boton('Editar')!.click();
    await estable();
    expect(dialogo()).not.toBeNull();
    const martes = el().querySelectorAll<HTMLInputElement>('dialog input[type="checkbox"]')[1]!;
    martes.click(); // agrega el martes
    await estable();
    boton('Guardar horario', dialogo()!)!.click();
    const req = backend.expectOne(`${API}/sesiones/horario`);
    expect(req.request.method).toBe('PUT');
    expect(req.request.body.dias.map((d: { dia_semana: number }) => d.dia_semana)).toEqual([0, 1, 2, 5]);
    expect(req.request.body.dias[2]).toEqual({ dia_semana: 2, hora_inicio: '18:00', hora_fin: '20:00', lugar: 'Coliseo' });
    req.flush({ ...HORARIO, creadas: 8, eliminadas: 0, canceladas: 0 });
    pedirSesiones().flush([]);
    await estable();
    expect(dialogo()).toBeNull();
    expect(texto()).toContain('Horario guardado');
  });

  it('rechazar una justificación pide el motivo en un popup', async () => {
    await cargarStaff([], null, [JUSTIFICACION]);
    boton('Rechazar')!.click();
    await estable();
    const enviar = boton('Rechazar', dialogo()!)!;
    expect(enviar.disabled).toBe(true);
    escribir('dialog input[formcontrolname="comentario"]', 'No trae soporte');
    await estable();
    expect(enviar.disabled).toBe(false);
    enviar.click();
    const req = backend.expectOne(`${API}/justificaciones/j1/revisar`);
    expect(req.request.body).toEqual({ aprobar: false, comentario: 'No trae soporte' });
    req.flush({ ...JUSTIFICACION, estado: 'rechazada' });
    await estable();
    expect(dialogo()).toBeNull();
    expect(texto()).toContain('No hay justificaciones pendientes');
  });

  it('la familia no ve alertas ni edita el horario, y justifica a su hijo en un popup', async () => {
    crear(FAMILIA);
    pedirSesiones().flush([sesion({ fecha: isoLocal(sumarDias(new Date(), -1)), cerrada: true })]);
    backend.expectOne(`${API}/sesiones/horario`).flush(HORARIO);
    const mias = backend.expectOne((r) => r.url === `${API}/justificaciones`);
    expect(mias.request.params.has('estado')).toBe(false);
    mias.flush([]);
    backend.expectNone(`${API}/sesiones/alertas`);
    backend.expectOne(`${API}/sesiones/s1/asistencia`).flush([fila('a1', 'Laura Pérez', { asistencia: 'ausente', multa: 'pendiente' })]);
    await estable();

    expect(el().querySelector('.marca')).toBeNull();
    expect(boton('Corregir')).toBeUndefined();
    expect(boton('Editar')).toBeUndefined();
    expect(boton('Marcar presente')).toBeUndefined(); // no es hoy
    boton('Justificar')!.click();
    await estable();
    escribir('dialog textarea', 'Estaba enferma con fiebre');
    await estable();
    boton('Enviar', dialogo()!)!.click();
    const req = backend.expectOne(`${API}/sesiones/s1/justificaciones`);
    expect(req.request.body).toEqual({ alumno_id: 'a1', motivo: 'Estaba enferma con fiebre' });
    req.flush({ ...JUSTIFICACION, alumno_id: 'a1' });
    backend.expectOne(`${API}/sesiones/s1/asistencia`).flush([fila('a1', 'Laura Pérez', { asistencia: 'ausente', justificacion: 'pendiente', multa: 'pendiente' })]);
    backend.expectOne((r) => r.url === `${API}/justificaciones`).flush([]);
    await estable();
    expect(texto()).toContain('Justificación enviada');
    expect(boton('Justificar')).toBeUndefined();
  });

  it('si la API rechaza, el error se muestra dentro del popup sin perder lo escrito', async () => {
    await cargarStaff([sesion()], [fila('a1', 'Laura Pérez')]);
    boton('Cancelar sesión')!.click();
    await estable();
    escribir('dialog input[formcontrolname="motivo"]', 'Evento del club');
    await estable();
    boton('Cancelar sesión', dialogo()!)!.click();
    backend.expectOne(`${API}/sesiones/s1/cancelar`).flush({ detail: 'La sesión ya estaba cancelada.' }, { status: 409, statusText: 'Conflict' });
    await estable();
    expect(dialogo()?.querySelector('[role="alert"]')?.textContent).toContain('La sesión ya estaba cancelada.');
    expect(dialogo()!.querySelector<HTMLInputElement>('input')!.value).toBe('Evento del club');
  });
});

describe('mensajeError', () => {
  it('usa el detalle de la API y oculta lo técnico', () => {
    const conDetalle = new HttpErrorResponse({ status: 422, error: { detail: [{ msg: 'Value error, Motivo corto' }] } });
    expect(mensajeError(conDetalle)).toBe('Motivo corto');
    expect(mensajeError(new HttpErrorResponse({ status: 0 }))).toContain('conexión');
    expect(mensajeError(new HttpErrorResponse({ status: 500, error: '<html>traza</html>' }))).not.toContain('traza');
  });
});
