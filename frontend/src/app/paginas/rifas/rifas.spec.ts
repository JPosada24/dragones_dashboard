import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { registerLocaleData } from '@angular/common';
import localeEsCo from '@angular/common/locales/es-CO';
import { LOCALE_ID } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { isoLocal, sumarDias } from '../../compartido/fechas';
import { AuthService } from '../../core/auth/auth.service';
import { API, Usuario } from '../../core/modelos';
import { RifasPage } from './rifas';
import { Rifa, Talonario } from './rifas.modelos';

registerLocaleData(localeEsCo);

const HOY = new Date();
const ANIO = HOY.getFullYear();
const SUPERADMIN = ['alumnos.ver_todos', 'rifas.gestionar', 'pagos.registrar', 'pagos.anular', 'sorteo.jugar'];
const ADMIN = ['alumnos.ver_todos', 'rifas.gestionar', 'pagos.registrar'];
const FAMILIA = ['alumnos.ver_propios'];

const rifa = (id: string, extra: Partial<Rifa> = {}): Rifa => ({
  id, nombre: `Rifa ${id}`, anio: ANIO, numero: Number(id), premio: 'Balón oficial',
  fecha_sorteo: isoLocal(sumarDias(HOY, 10)), puestos_por_talonario: 20, precio_puesto: 2000, valor_talonario: 40000,
  estado: 'abierta', motivo_cancelacion: null, talonarios: 2, talonarios_pagados: 1, recaudado: 50000, esperado: 80000,
  ...extra,
});

const talonario = (id: string, alumno: string, codigo: string, recaudado: number): Talonario => ({
  id, alumno_id: `a-${alumno}`, alumno_nombre: alumno, rama: 'femenina', codigo, boletas: 20, recaudado,
  saldo: 40000 - recaudado, pagado: recaudado >= 40000,
  pagos: recaudado ? [{ id: `p-${id}`, fecha: isoLocal(HOY), monto: recaudado, anula_id: null, motivo: null, creado_en: '' }] : [],
});

describe('RifasPage', () => {
  let backend: HttpTestingController;
  let fixture: ComponentFixture<RifasPage>;

  function crear(permisos: string[]) {
    TestBed.configureTestingModule({
      imports: [RifasPage],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting(), { provide: LOCALE_ID, useValue: 'es-CO' }],
    });
    const usuario: Usuario = { id: 'u', email: 'x@club.com', nombre: 'X', rol: 'ADMIN', activo: true, rama: null, permisos };
    TestBed.inject(AuthService).usuario.set(usuario);
    backend = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(RifasPage);
    fixture.detectChanges();
  }

  afterEach(() => backend.verify());

  const el = () => fixture.nativeElement as HTMLElement;
  const texto = () => el().textContent ?? '';
  const boton = (t: string, dentro: ParentNode = el()) =>
    [...dentro.querySelectorAll('button')].find((b) => b.textContent?.replace(/\s+/g, ' ').trim().startsWith(t)) as HTMLButtonElement | undefined;
  const dialogos = () => [...el().querySelectorAll('dialog')];
  const ultimo = () => dialogos().at(-1)!;
  async function estable() {
    await fixture.whenStable();
    fixture.detectChanges();
  }
  async function cargar(permisos: string[], rifas = [rifa('1'), rifa('2', { estado: 'cancelada', motivo_cancelacion: null })]) {
    crear(permisos);
    const r = backend.expectOne((x) => x.url === `${API}/rifas`);
    expect(r.request.params.get('anio')).toBe(String(ANIO));
    r.flush(rifas);
    // Solo se piden los talonarios de las rifas no canceladas.
    backend.expectOne(`${API}/rifas/1/talonarios`).flush([talonario('t1', 'Laura Pérez', 'F001', 40000), talonario('t2', 'Sara Ríos', 'F002', 10000)]);
    backend.expectNone(`${API}/rifas/2/talonarios`);
    await estable();
  }
  async function abrirTalonarioDeSara() {
    el().querySelector<HTMLButtonElement>('[aria-label^="Rifa 1: debe"]')!.click();
    await estable();
  }

  it('muestra las rifas del año y la matriz de paz y salvo por alumno', async () => {
    await cargar(ADMIN);
    expect(el().querySelectorAll('.tarjeta').length).toBe(2);
    const filas = [...el().querySelectorAll('tbody tr')].map((f) => f.textContent?.replace(/\s+/g, ' '));
    expect(filas[0]).toContain('Laura Pérez');
    expect(filas[0]).toContain('F001');
    expect(filas[1]).toContain('$30.000');
    boton('Con deuda')!.click();
    await estable();
    expect(el().querySelectorAll('tbody tr').length).toBe(1);
  });

  it('el talonario es del alumno: muestra sus boletas por código y registra un pago o abono', async () => {
    await cargar(ADMIN);
    await abrirTalonarioDeSara();
    expect(ultimo().textContent).toContain('Talonario de Sara Ríos');
    expect(ultimo().textContent).toContain('boletas F002-01 a F002-20');
    expect(ultimo().textContent).not.toContain('comprador');
    boton('payments Registrar pago', ultimo())!.click();
    await estable();
    const monto = ultimo().querySelector<HTMLInputElement>('[formcontrolname="monto"]')!;
    expect(monto.value).toBe('');
    boton('Usar el saldo completo', ultimo())!.click();
    await estable();
    expect(monto.value).toBe('30000');
    boton('Registrar', ultimo().querySelector('form')!)!.click();
    const pago = backend.expectOne(`${API}/rifas/1/talonarios/t2/pagos`);
    expect(pago.request.body).toEqual({ monto: 30000, fecha: isoLocal(HOY) });
    pago.flush(talonario('t2', 'Sara Ríos', 'F002', 40000));
    backend.expectOne(`${API}/rifas/1`).flush(rifa('1', { talonarios_pagados: 2, recaudado: 80000 }));
    await estable();
    expect(texto()).toContain('queda a paz y salvo');
  });

  it('solo el SuperAdmin anula pagos, y sin necesidad de motivo', async () => {
    await cargar(ADMIN);
    await abrirTalonarioDeSara();
    expect(boton('Anular', ultimo())).toBeUndefined();
    TestBed.resetTestingModule();

    await cargar(SUPERADMIN);
    await abrirTalonarioDeSara();
    boton('Anular', ultimo())!.click();
    await estable();
    boton('Anular pago', ultimo())!.click();
    const r = backend.expectOne(`${API}/rifas/1/talonarios/t2/pagos/p-t2/anular`);
    expect(r.request.body).toEqual({ motivo: null });
    r.flush(talonario('t2', 'Sara Ríos', 'F002', 0));
    backend.expectOne(`${API}/rifas/1`).flush(rifa('1'));
    await estable();
    expect(texto()).toContain('Pago anulado');
  });

  it('cancelar no pide motivo y eliminar avisa si solo el SuperAdmin puede', async () => {
    await cargar(ADMIN, [rifa('1')]);
    boton('Cancelar', el().querySelector('.tarjeta')!)!.click();
    await estable();
    boton('Cancelar rifa', ultimo())!.click();
    const c = backend.expectOne(`${API}/rifas/1/cancelar`);
    expect(c.request.body).toEqual({ motivo: null });
    c.flush(rifa('1', { estado: 'cancelada' }));
    backend.expectOne((x) => x.method === 'GET' && x.url === `${API}/rifas`).flush([rifa('1', { estado: 'cancelada' })]);
    await estable();

    el().querySelector<HTMLButtonElement>('[aria-label="Eliminar Rifa 1"]')!.click();
    await estable();
    expect(ultimo().textContent).toContain('solo el SuperAdmin'); // ya tiene pagos
    boton('Eliminar rifa', ultimo())!.click();
    backend.expectOne((x) => x.method === 'DELETE' && x.url === `${API}/rifas/1`)
      .flush({ detail: 'Esta rifa ya tiene pagos o sorteos: solo el SuperAdmin puede eliminarla.' }, { status: 403, statusText: 'Forbidden' });
    await estable();
    expect(ultimo().querySelector('[role="alert"]')?.textContent).toBeTruthy();
  });

  it('eliminar una rifa la quita de la pantalla', async () => {
    crear(SUPERADMIN);
    backend.expectOne((x) => x.url === `${API}/rifas`).flush([rifa('1', { recaudado: 0, talonarios_pagados: 0 })]);
    backend.expectOne(`${API}/rifas/1/talonarios`).flush([]);
    await estable();
    el().querySelector<HTMLButtonElement>('[aria-label="Eliminar Rifa 1"]')!.click();
    await estable();
    boton('Eliminar rifa', ultimo())!.click();
    backend.expectOne((x) => x.method === 'DELETE' && x.url === `${API}/rifas/1`).flush(null, { status: 204, statusText: 'No Content' });
    backend.expectOne((x) => x.method === 'GET' && x.url === `${API}/rifas`).flush([]);
    await estable();
    expect(texto()).toContain('«Rifa 1» eliminada');
    expect(el().querySelectorAll('.tarjeta').length).toBe(0);
  });

  it('la tarjeta lleva al sorteo cuando ya es la fecha', async () => {
    await cargar(SUPERADMIN, [rifa('1')]);
    expect(el().querySelector('.tarjeta a[href*="/rifas/sorteo"]')).toBeNull(); // aún no es la fecha
    TestBed.resetTestingModule();
    await cargar(SUPERADMIN, [rifa('1', { fecha_sorteo: isoLocal(HOY) })]);
    expect(el().querySelector('a[href="/rifas/sorteo?rifa=1"]')?.textContent).toContain('Ir al sorteo');
  });

  it('la familia ve su talonario sin botones de cobro ni gestión', async () => {
    crear(FAMILIA);
    backend.expectOne((x) => x.url === `${API}/rifas`).flush([rifa('1')]);
    backend.expectOne(`${API}/rifas/1/talonarios`).flush([talonario('t2', 'Sara Ríos', 'F002', 10000)]);
    await estable();
    expect(el().querySelector('.kpis')).toBeNull();
    expect(boton('add Nueva rifa')).toBeUndefined();
    expect(el().querySelector('[aria-label^="Eliminar"]')).toBeNull();
    el().querySelector<HTMLButtonElement>('.celda')!.click();
    await estable();
    expect(boton('payments Registrar pago', ultimo())).toBeUndefined();
  });

  it('crea una rifa nueva', async () => {
    crear(ADMIN);
    backend.expectOne((x) => x.url === `${API}/rifas`).flush([]);
    await estable();
    expect(texto()).toContain('No hay rifas en');
    boton('add Nueva rifa')!.click();
    await estable();
    const premio = ultimo().querySelector<HTMLInputElement>('[formcontrolname="premio"]')!;
    premio.value = 'Uniforme completo';
    premio.dispatchEvent(new Event('input'));
    const fecha = ultimo().querySelector<HTMLInputElement>('[formcontrolname="fecha_sorteo"]')!;
    fecha.value = isoLocal(sumarDias(HOY, 30));
    fecha.dispatchEvent(new Event('input'));
    boton('Crear rifa', ultimo())!.click();
    const r = backend.expectOne((x) => x.method === 'POST' && x.url === `${API}/rifas`);
    expect(r.request.body).toMatchObject({ nombre: `Rifa 1 de ${ANIO}`, premio: 'Uniforme completo', anio: ANIO });
    r.flush(rifa('3', { talonarios: 12 }));
    backend.expectOne((x) => x.method === 'GET' && x.url === `${API}/rifas`).flush([rifa('3')]);
    backend.expectOne(`${API}/rifas/3/talonarios`).flush([]);
    await estable();
    expect(texto()).toContain('creada con 12 talonarios');
  });
});
