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
import { FilaPlanilla, Justificacion, Sesion } from './asistencia.modelos';

registerLocaleData(localeEsCo);

const HOY = isoLocal(new Date());
const STAFF = [
  'alumnos.ver_todos', 'asistencia.marcar_grupo', 'asistencia.corregir', 'justificaciones.revisar', 'sesiones.gestionar',
];
const FAMILIA = ['alumnos.ver_propios', 'asistencia.marcar_propia'];

const sesion = (extra: Partial<Sesion> = {}): Sesion => ({
  id: 's1', rama: 'femenina', fecha: HOY, hora_inicio: '18:00:00', hora_fin: '20:00:00', lugar: 'Cancha 2',
  cancelada: false, motivo_cancelacion: null, cerrada: false, ...extra,
});

const fila = (id: string, nombre: string, extra: Partial<FilaPlanilla> = {}): FilaPlanilla => ({
  alumno_id: id, alumno_nombre: nombre, asistencia: null, justificacion: null, multa: null, ...extra,
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
  const boton = (t: string) =>
    [...el().querySelectorAll('button')].find((b) => b.textContent?.trim() === t) as HTMLButtonElement | undefined;
  const pedirSesiones = (): TestRequest => backend.expectOne((r) => r.url === `${API}/sesiones`);
  async function estable() {
    await fixture.whenStable();
    fixture.detectChanges();
  }

  afterEach(() => backend.verify());

  it('el staff marca la planilla de hoy y la guarda', async () => {
    crear(STAFF);
    const req = pedirSesiones();
    expect(req.request.params.get('desde')).toBe(isoLocal(lunesDe(new Date())));
    expect(req.request.params.get('hasta')).toBe(isoLocal(sumarDias(lunesDe(new Date()), 6)));
    req.flush([sesion()]);
    backend.expectOne((r) => r.url === `${API}/justificaciones`).flush([]);
    backend.expectOne(`${API}/sesiones/alertas`).flush([{ alumno_id: 'a3', alumno_nombre: 'Kevin Ruiz', rama: 'masculina', inasistencias_seguidas: 3 }]);
    backend.expectOne(`${API}/sesiones/s1/asistencia`).flush([fila('a1', 'Laura Pérez'), fila('a2', 'Ana Díaz')]);
    await estable();

    expect(texto()).toContain('Laura Pérez');
    expect(texto()).toContain('3 seguidas');
    expect(boton('Guardar planilla')?.disabled).toBe(true);

    boton('Todos presentes')!.click();
    el().querySelector<HTMLButtonElement>('[aria-label="Ausente: Ana Díaz"]')!.click();
    await estable();

    boton('Guardar planilla')!.click();
    const guardar = backend.expectOne(`${API}/sesiones/s1/asistencia`);
    expect(guardar.request.method).toBe('POST');
    expect(guardar.request.body).toEqual({
      marcas: [{ alumno_id: 'a1', estado: 'presente' }, { alumno_id: 'a2', estado: 'ausente' }],
    });
    guardar.flush([fila('a1', 'Laura Pérez', { asistencia: 'presente' }), fila('a2', 'Ana Díaz', { asistencia: 'ausente' })]);
    await estable();
    expect(texto()).toContain('Planilla guardada (2 marcas)');
  });

  it('una sesión futura no deja marcar', async () => {
    crear(STAFF);
    pedirSesiones().flush([sesion({ fecha: isoLocal(sumarDias(new Date(), 1)) })]);
    backend.expectOne((r) => r.url === `${API}/justificaciones`).flush([]);
    backend.expectOne(`${API}/sesiones/alertas`).flush([]);
    backend.expectOne(`${API}/sesiones/s1/asistencia`).flush([fila('a1', 'Laura Pérez')]);
    await estable();
    expect(el().querySelector('.marca')).toBeNull();
    expect(boton('Guardar planilla')).toBeUndefined();
  });

  it('rechazar una justificación exige el motivo', async () => {
    crear(STAFF);
    pedirSesiones().flush([]);
    const pend = backend.expectOne((r) => r.url === `${API}/justificaciones`);
    expect(pend.request.params.get('estado')).toBe('pendiente');
    pend.flush([JUSTIFICACION]);
    backend.expectOne(`${API}/sesiones/alertas`).flush([]);
    await estable();

    boton('Rechazar')!.click(); // abre el formulario
    await estable();
    const enviar = [...el().querySelectorAll<HTMLButtonElement>('button[type="submit"]')].find((b) => b.textContent?.includes('Rechazar'))!;
    expect(enviar.disabled).toBe(true);

    const input = el().querySelector<HTMLInputElement>('input[formcontrolname="comentario"]')!;
    input.value = 'No trae soporte';
    input.dispatchEvent(new Event('input'));
    await estable();
    expect(enviar.disabled).toBe(false);
    enviar.click();
    const req = backend.expectOne(`${API}/justificaciones/j1/revisar`);
    expect(req.request.body).toEqual({ aprobar: false, comentario: 'No trae soporte' });
    req.flush({ ...JUSTIFICACION, estado: 'rechazada' });
    await estable();
    expect(texto()).toContain('No hay justificaciones pendientes');
  });

  it('la familia no pide alertas ni pendientes del club, y justifica a su hijo', async () => {
    crear(FAMILIA);
    pedirSesiones().flush([sesion({ fecha: isoLocal(sumarDias(new Date(), -1)), cerrada: true })]);
    const mias = backend.expectOne((r) => r.url === `${API}/justificaciones`);
    expect(mias.request.params.has('estado')).toBe(false);
    mias.flush([]);
    backend.expectNone(`${API}/sesiones/alertas`);
    backend.expectOne(`${API}/sesiones/s1/asistencia`).flush([fila('a1', 'Laura Pérez', { asistencia: 'ausente', multa: 'pendiente' })]);
    await estable();

    expect(el().querySelector('.marca')).toBeNull();
    expect(boton('Corregir')).toBeUndefined();
    expect(boton('Marcar presente')).toBeUndefined(); // no es hoy
    boton('Justificar')!.click();
    await estable();
    const area = el().querySelector<HTMLTextAreaElement>('textarea')!;
    area.value = 'Estaba enferma con fiebre';
    area.dispatchEvent(new Event('input'));
    await estable();
    boton('Enviar')!.click();
    const req = backend.expectOne(`${API}/sesiones/s1/justificaciones`);
    expect(req.request.body).toEqual({ alumno_id: 'a1', motivo: 'Estaba enferma con fiebre' });
    req.flush({ ...JUSTIFICACION, alumno_id: 'a1' });
    backend.expectOne(`${API}/sesiones/s1/asistencia`).flush([fila('a1', 'Laura Pérez', { asistencia: 'ausente', justificacion: 'pendiente', multa: 'pendiente' })]);
    backend.expectOne((r) => r.url === `${API}/justificaciones`).flush([]);
    await estable();
    expect(texto()).toContain('Justificación enviada');
    expect(boton('Justificar')).toBeUndefined();
  });

  it('muestra el mensaje de la API cuando una acción falla', async () => {
    crear(STAFF);
    pedirSesiones().flush([sesion()]);
    backend.expectOne((r) => r.url === `${API}/justificaciones`).flush([]);
    backend.expectOne(`${API}/sesiones/alertas`).flush([]);
    backend.expectOne(`${API}/sesiones/s1/asistencia`).flush([fila('a1', 'Laura Pérez')]);
    await estable();
    el().querySelector<HTMLButtonElement>('[aria-label="Presente: Laura Pérez"]')!.click();
    await estable();
    boton('Guardar planilla')!.click();
    backend.expectOne(`${API}/sesiones/s1/asistencia`).flush({ detail: 'La sesión ya fue cerrada.' }, { status: 409, statusText: 'Conflict' });
    await estable();
    expect(el().querySelector('[role="alert"]')?.textContent).toContain('La sesión ya fue cerrada.');
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
