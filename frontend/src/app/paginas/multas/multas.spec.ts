import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, TestRequest, provideHttpClientTesting } from '@angular/common/http/testing';
import { registerLocaleData } from '@angular/common';
import localeEsCo from '@angular/common/locales/es-CO';
import { LOCALE_ID } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { isoLocal, sumarDias } from '../../compartido/fechas';
import { AuthService } from '../../core/auth/auth.service';
import { API, Usuario } from '../../core/modelos';
import { MultasPage } from './multas';
import { Multa, SituacionMora } from './multas.modelos';

registerLocaleData(localeEsCo);

const HOY = new Date();
const ADMIN = ['alumnos.ver_todos', 'pagos.registrar', 'multas.anular'];
const ENTRENADOR = ['alumnos.ver_rama'];
const FAMILIA = ['alumnos.ver_propios'];

const multa = (id: string, alumno: string, extra: Partial<Multa> = {}): Multa => ({
  id, alumno_id: `a-${alumno}`, alumno_nombre: alumno, rama: 'femenina', sesion_id: `s-${id}`,
  fecha_sesion: isoLocal(sumarDias(HOY, -Number(id))), valor: 2000, estado: 'pendiente', fecha_pago: null,
  motivo_anulacion: null, ...extra,
});

const MULTAS = [multa('1', 'Laura Pérez'), multa('2', 'Sara Ríos'), multa('3', 'Laura Pérez')];
const MORA: SituacionMora[] = [
  { alumno_id: 'a-x', alumno_nombre: 'Kevin Gil', rama: 'masculina', total_vencido: 6000, vencida_desde: '2026-06-01',
    entra_en_mora: isoLocal(sumarDias(HOY, 12)), en_mora: false, deudas: [{ concepto: 'Multa 1 jun', monto: 6000, vence: '2026-06-01' }] },
  { alumno_id: 'a-y', alumno_nombre: 'Ana Ruiz', rama: 'femenina', total_vencido: 40000, vencida_desde: '2026-05-01',
    entra_en_mora: '2026-08-01', en_mora: true, deudas: [{ concepto: 'Talonario de «Rifa 1»', monto: 40000, vence: '2026-05-01' }] },
];

describe('MultasPage', () => {
  let backend: HttpTestingController;
  let fixture: ComponentFixture<MultasPage>;

  function crear(permisos: string[]) {
    TestBed.configureTestingModule({
      imports: [MultasPage],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting(), { provide: LOCALE_ID, useValue: 'es-CO' }],
    });
    const usuario: Usuario = { id: 'u', email: 'x@club.com', nombre: 'X', rol: 'ADMIN', activo: true, rama: null, permisos };
    TestBed.inject(AuthService).usuario.set(usuario);
    backend = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(MultasPage);
    fixture.detectChanges();
  }

  afterEach(() => backend.verify());

  const el = () => fixture.nativeElement as HTMLElement;
  const texto = () => el().textContent ?? '';
  const boton = (t: string, dentro: ParentNode = el()) =>
    [...dentro.querySelectorAll('button')].find((b) => b.textContent?.trim().startsWith(t)) as HTMLButtonElement | undefined;
  const dialogo = () => el().querySelector('dialog')!;
  const pedirMultas = (): TestRequest => backend.expectOne((r) => r.url === `${API}/multas` && r.method === 'GET');
  async function estable() {
    await fixture.whenStable();
    fixture.detectChanges();
  }
  async function cargarStaff(permisos = ADMIN) {
    crear(permisos);
    const r = pedirMultas();
    expect(r.request.params.get('estado')).toBe('pendiente');
    r.flush(MULTAS);
    backend.expectOne(`${API}/mora`).flush(MORA);
    await estable();
  }

  it('agrupa las pendientes por alumno (quien más debe primero) y muestra la mora', async () => {
    await cargarStaff();
    const grupos = [...el().querySelectorAll('.grupo-cabecera')].map((g) => g.textContent?.replace(/\s+/g, ' ').trim());
    expect(grupos[0]).toContain('Laura Pérez');
    expect(grupos[0]).toContain('$4.000');
    expect(el().querySelector('.kpis')!.textContent).toContain('$6.000');
    // En mora primero; el que está en riesgo dice en cuántos días entra.
    const situaciones = [...el().querySelectorAll('.situacion')];
    expect(situaciones[0]!.textContent).toContain('En mora');
    expect(situaciones[1]!.textContent).toContain('Entra en mora en 12 d');
  });

  it('cobra todas las multas de un alumno en un solo pago', async () => {
    await cargarStaff();
    boton('Cobrar todo')!.click();
    await estable();
    expect(dialogo().textContent).toContain('$4.000');
    boton('Registrar pago', dialogo())!.click();
    const pago = backend.expectOne(`${API}/multas/pagos`);
    expect(pago.request.body).toEqual({ multa_ids: ['1', '3'], fecha_pago: isoLocal(HOY) });
    pago.flush([{ ...MULTAS[0]!, estado: 'pagada' }, { ...MULTAS[2]!, estado: 'pagada' }]);
    backend.expectOne(`${API}/mora`).flush([]);
    await estable();
    expect(texto()).toContain('2 multas cobradas a Laura Pérez: $4.000');
    expect(el().querySelectorAll('.grupo').length).toBe(1);
  });

  it('anular no exige motivo y el error de la API se ve en el popup', async () => {
    await cargarStaff();
    boton('Anular')!.click();
    await estable();
    boton('Anular multa', dialogo())!.click();
    const r = backend.expectOne(`${API}/multas/1/anular`);
    expect(r.request.body).toEqual({ motivo: null });
    r.flush({ detail: 'Solo se puede anular una multa pendiente.' }, { status: 409, statusText: 'Conflict' });
    await estable();
    expect(dialogo().querySelector('[role="alert"]')?.textContent).toContain('Solo se puede anular');
  });

  it('el entrenador ve multas y mora de su rama, pero no cobra ni anula', async () => {
    await cargarStaff(ENTRENADOR);
    expect(boton('Cobrar')).toBeUndefined();
    expect(boton('Anular')).toBeUndefined();
    expect(boton('Femenina')).toBeUndefined();
    expect(el().querySelectorAll('.situacion').length).toBe(2);
  });

  it('la familia ve sus multas, sin mora ni indicadores', async () => {
    crear(FAMILIA);
    pedirMultas().flush([multa('1', 'Laura Pérez')]);
    backend.expectNone(`${API}/mora`);
    await estable();
    expect(el().querySelector('.kpis')).toBeNull();
    expect(texto()).toContain('Laura Pérez');
    expect(boton('Cobrar')).toBeUndefined();
  });

  it('el historial de pagadas se pide al cambiar de filtro', async () => {
    await cargarStaff();
    boton('Pagadas')!.click();
    const r = pedirMultas();
    expect(r.request.params.get('estado')).toBe('pagada');
    r.flush([multa('5', 'Sara Ríos', { estado: 'pagada', fecha_pago: isoLocal(HOY) })]);
    await estable();
    expect(el().querySelector('.historial')!.textContent).toContain('Pagada el');
  });
});
