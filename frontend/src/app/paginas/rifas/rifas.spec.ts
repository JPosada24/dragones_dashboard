import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { registerLocaleData } from '@angular/common';
import localeEsCo from '@angular/common/locales/es-CO';
import { LOCALE_ID } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { isoLocal, sumarDias } from '../../compartido/fechas';
import { AuthService } from '../../core/auth/auth.service';
import { API, Usuario } from '../../core/modelos';
import { RifasPage } from './rifas';
import { Acta, Puesto, Rifa, Talonario } from './rifas.modelos';

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

const puestos = (desde: number, pagados: number): Puesto[] =>
  Array.from({ length: 20 }, (_, i) => ({
    numero: desde + i, comprador_nombre: i === 0 ? 'Doña Rosa' : null, comprador_telefono: null,
    monto_pagado: i < pagados ? 2000 : 0, saldo: i < pagados ? 0 : 2000,
    pagos: i < pagados ? [{ id: `p${desde + i}`, fecha: isoLocal(HOY), monto: 2000, anula_id: null, motivo: null, creado_en: '' }] : [],
  }));

const talonario = (id: string, alumno: string, desde: number, pagados: number): Talonario => ({
  id, alumno_id: `a-${alumno}`, alumno_nombre: alumno, rama: 'femenina', desde, hasta: desde + 19,
  recaudado: pagados * 2000, saldo: (20 - pagados) * 2000, pagado: pagados === 20, puestos: puestos(desde, pagados),
});

describe('RifasPage', () => {
  let backend: HttpTestingController;
  let fixture: ComponentFixture<RifasPage>;

  function crear(permisos: string[]) {
    TestBed.configureTestingModule({
      imports: [RifasPage],
      providers: [provideHttpClient(), provideHttpClientTesting(), { provide: LOCALE_ID, useValue: 'es-CO' }],
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
  async function cargar(permisos: string[], rifas = [rifa('1'), rifa('2', { estado: 'cancelada', motivo_cancelacion: 'Lluvia' })]) {
    crear(permisos);
    const r = backend.expectOne((x) => x.url === `${API}/rifas`);
    expect(r.request.params.get('anio')).toBe(String(ANIO));
    r.flush(rifas);
    // Solo se piden los talonarios de las rifas no canceladas.
    backend.expectOne(`${API}/rifas/1/talonarios`).flush([talonario('t1', 'Laura Pérez', 0, 20), talonario('t2', 'Sara Ríos', 20, 5)]);
    backend.expectNone(`${API}/rifas/2/talonarios`);
    await estable();
  }

  it('muestra las rifas del año y la matriz de paz y salvo por alumno', async () => {
    await cargar(ADMIN);
    expect(el().querySelectorAll('.tarjeta').length).toBe(2);
    expect(texto()).toContain('Lluvia');
    const filas = [...el().querySelectorAll('tbody tr')].map((f) => f.textContent?.replace(/\s+/g, ' '));
    expect(filas[0]).toContain('Laura Pérez');
    expect(filas[1]).toContain('$30.000'); // Sara debe 15 puestos
    boton('Con deuda')!.click();
    await estable();
    expect(el().querySelectorAll('tbody tr').length).toBe(1);
  });

  it('abre el talonario y registra un pago que se reparte entre los puestos', async () => {
    await cargar(ADMIN);
    el().querySelector<HTMLButtonElement>('[aria-label^="Rifa 1: debe"]')!.click();
    await estable();
    expect(ultimo().textContent).toContain('Talonario de Sara Ríos');
    expect(ultimo().querySelectorAll('.puesto').length).toBe(20);
    boton('payments Registrar pago', ultimo())!.click();
    await estable();
    expect(ultimo().querySelector<HTMLInputElement>('[formcontrolname="monto"]')!.value).toBe('30000');
    boton('Registrar', ultimo().querySelector('form')!)!.click();
    const pago = backend.expectOne(`${API}/rifas/1/talonarios/t2/pagos`);
    expect(pago.request.body).toEqual({ monto: 30000, fecha: isoLocal(HOY) });
    pago.flush(talonario('t2', 'Sara Ríos', 20, 20));
    backend.expectOne(`${API}/rifas/1`).flush(rifa('1', { talonarios_pagados: 2, recaudado: 80000 }));
    await estable();
    expect(texto()).toContain('queda a paz y salvo');
  });

  it('el comprador de un puesto se guarda desde su popup', async () => {
    await cargar(ADMIN);
    el().querySelector<HTMLButtonElement>('[aria-label^="Rifa 1: debe"]')!.click();
    await estable();
    el().querySelector<HTMLButtonElement>('[aria-label^="Puesto 025"]')!.click();
    await estable();
    const nombre = ultimo().querySelector<HTMLInputElement>('[formcontrolname="nombre"]')!;
    nombre.value = 'Carlos Mejía';
    nombre.dispatchEvent(new Event('input'));
    boton('Guardar comprador', ultimo())!.click();
    const r = backend.expectOne((x) => x.method === 'PATCH' && x.url === `${API}/rifas/1/puestos/25`);
    expect(r.request.body).toEqual({ nombre: 'Carlos Mejía', telefono: null });
    r.flush(talonario('t2', 'Sara Ríos', 20, 5));
    backend.expectOne(`${API}/rifas/1`).flush(rifa('1'));
    await estable();
    expect(texto()).toContain('Puesto 025: comprador guardado');
  });

  it('solo el SuperAdmin anula pagos de un puesto', async () => {
    await cargar(ADMIN);
    el().querySelector<HTMLButtonElement>('[aria-label^="Rifa 1: debe"]')!.click();
    await estable();
    el().querySelector<HTMLButtonElement>('[aria-label^="Puesto 020"]')!.click();
    await estable();
    expect(boton('Anular', ultimo())).toBeUndefined();
    TestBed.resetTestingModule();

    await cargar(SUPERADMIN);
    el().querySelector<HTMLButtonElement>('[aria-label^="Rifa 1: debe"]')!.click();
    await estable();
    el().querySelector<HTMLButtonElement>('[aria-label^="Puesto 020"]')!.click();
    await estable();
    boton('Anular', ultimo())!.click();
    await estable();
    const motivo = ultimo().querySelector('textarea')!;
    motivo.value = 'Se registró en el puesto equivocado';
    motivo.dispatchEvent(new Event('input'));
    boton('Anular pago', ultimo())!.click();
    const r = backend.expectOne(`${API}/rifas/1/puestos/20/pagos/p20/anular`);
    expect(r.request.body).toEqual({ motivo: 'Se registró en el puesto equivocado' });
    r.flush(talonario('t2', 'Sara Ríos', 20, 4));
    backend.expectOne(`${API}/rifas/1`).flush(rifa('1'));
    await estable();
    expect(texto()).toContain('Pago anulado');
  });

  it('el sorteo se juega desde la fecha y muestra el acta', async () => {
    await cargar(SUPERADMIN, [rifa('1')]);
    expect(boton('casino Jugar sorteo')).toBeUndefined(); // aún no es la fecha
    TestBed.resetTestingModule();

    await cargar(SUPERADMIN, [rifa('1', { fecha_sorteo: isoLocal(HOY) })]);
    boton('casino Jugar sorteo')!.click();
    await estable();
    expect(ultimo().querySelector('.urna-valor')?.textContent?.trim()).toBe('20');
    boton('casino Jugar sorteo', ultimo())!.click();
    const acta: Acta = {
      rifa_id: '1', numero_ganador: 7, alumno_id: 'a-Laura Pérez', alumno_nombre: 'Laura Pérez', comprador_nombre: 'Doña Rosa',
      total_participantes: 20, participantes: [], huella: 'abc123', jugado_en: new Date().toISOString(),
    };
    backend.expectOne(`${API}/rifas/1/sorteo`).flush(acta);
    backend.expectOne(`${API}/rifas/1`).flush(rifa('1', { estado: 'sorteada' }));
    await estable();
    expect(ultimo().querySelector('.ganador-numero')?.textContent?.trim()).toBe('007');
    expect(ultimo().textContent).toContain('Doña Rosa');
    expect(ultimo().textContent).toContain('abc123');
  });

  it('la familia ve su talonario sin botones de cobro ni gestión', async () => {
    crear(FAMILIA);
    backend.expectOne((x) => x.url === `${API}/rifas`).flush([rifa('1')]);
    backend.expectOne(`${API}/rifas/1/talonarios`).flush([talonario('t2', 'Sara Ríos', 20, 5)]);
    await estable();
    expect(el().querySelector('.kpis')).toBeNull();
    expect(boton('add Nueva rifa')).toBeUndefined();
    expect(boton('Asignar a nuevos')).toBeUndefined();
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
