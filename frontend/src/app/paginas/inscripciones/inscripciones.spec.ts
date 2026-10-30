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
import { InscripcionesPage } from './inscripciones';
import { Inscripcion } from './inscripciones.modelos';

registerLocaleData(localeEsCo);

const HOY = new Date();
const ANIO = HOY.getFullYear();
const ADMIN = ['alumnos.ver_todos', 'inscripciones.crear', 'inscripciones.abonar', 'inscripciones.gestionar', 'prorroga.conceder'];
const SUPERADMIN = [...ADMIN, 'pagos.anular', 'expulsion.confirmar'];
const FAMILIA = ['alumnos.ver_propios'];

const insc = (id: string, extra: Partial<Inscripcion> = {}): Inscripcion => ({
  id, alumno_id: `a-${id}`, alumno_nombre: `Alumno ${id}`, anio: ANIO, rama: 'femenina',
  fecha_inscripcion: isoLocal(sumarDias(HOY, -20)), fecha_limite_pago: isoLocal(sumarDias(HOY, 10)),
  valor: 90000, fecha_pago: null, monto_pagado: null, saldo: 90000, estado: 'pendiente_pago',
  causa_rechazo: null, causa_expulsion: null, motivo: null, prorrogas: [], pagos: [], ...extra,
});

const LISTA = [
  insc('1'),
  insc('2', { fecha_limite_pago: isoLocal(sumarDias(HOY, 3)), monto_pagado: 40000, saldo: 50000 }),
  insc('3', { estado: 'activo', monto_pagado: 90000, saldo: 0 }),
  insc('4', { estado: 'a_expulsar', monto_pagado: 90000, saldo: 0, causa_expulsion: 'mora' }),
];

describe('InscripcionesPage', () => {
  let backend: HttpTestingController;
  let fixture: ComponentFixture<InscripcionesPage>;

  function crear(permisos: string[]) {
    TestBed.configureTestingModule({
      imports: [InscripcionesPage],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting(), { provide: LOCALE_ID, useValue: 'es-CO' }],
    });
    const usuario: Usuario = { id: 'u', email: 'x@club.com', nombre: 'X', rol: 'ADMIN', activo: true, permisos };
    TestBed.inject(AuthService).usuario.set(usuario);
    backend = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(InscripcionesPage);
    fixture.detectChanges();
  }

  afterEach(() => backend.verify());

  const el = () => fixture.nativeElement as HTMLElement;
  const texto = () => el().textContent ?? '';
  const boton = (t: string, dentro: ParentNode = el()) =>
    [...dentro.querySelectorAll('button')].find((b) => b.textContent?.trim().startsWith(t)) as HTMLButtonElement | undefined;
  const dialogos = () => [...el().querySelectorAll('dialog')];
  const ultimoDialogo = () => dialogos().at(-1)!;
  const nombres = () => [...el().querySelectorAll('.fila .alumno-nombre')].map((n) => n.textContent?.trim());
  const pedirLista = (): TestRequest => backend.expectOne((r) => r.url === `${API}/inscripciones` && r.method === 'GET');
  async function estable() {
    await fixture.whenStable();
    fixture.detectChanges();
  }
  async function cargar(permisos: string[], lista = LISTA) {
    crear(permisos);
    const r = pedirLista();
    expect(r.request.params.get('anio')).toBe(String(ANIO));
    r.flush(lista);
    await estable();
  }
  function escribir(campo: HTMLInputElement | HTMLTextAreaElement, valor: string) {
    campo.value = valor;
    campo.dispatchEvent(new Event('input'));
  }

  it('muestra indicadores y por defecto las pendientes, la más urgente primero', async () => {
    await cargar(ADMIN);
    const kpis = el().querySelector('.kpis')!.textContent ?? '';
    expect(kpis).toContain('$140.000 por cobrar');
    expect(nombres()).toEqual(['Alumno 2', 'Alumno 1']);
    expect(texto()).toContain('3 d');

    boton('En revisión')!.click();
    await estable();
    expect(nombres()).toEqual(['Alumno 4']);
  });

  it('registra un abono desde la fila: el valor empieza vacío y la fecha vacía es hoy', async () => {
    await cargar(ADMIN);
    el().querySelector<HTMLButtonElement>('[aria-label="Registrar abono de Alumno 2"]')!.click();
    await estable();
    const monto = ultimoDialogo().querySelector<HTMLInputElement>('[formcontrolname="monto"]')!;
    expect(monto.value).toBe('');
    expect(monto.placeholder).toBe('Saldo: $50.000');
    boton('Usar el saldo completo', ultimoDialogo())!.click();
    await estable();
    expect(monto.value).toBe('50000');
    escribir(monto, '20000');
    boton('Registrar', ultimoDialogo())!.click();
    const pago = backend.expectOne(`${API}/inscripciones/2/pagos`);
    expect(pago.request.body).toEqual({ monto: 20000, fecha_pago: isoLocal(HOY) });
    pago.flush(insc('2', { fecha_limite_pago: LISTA[1]!.fecha_limite_pago, monto_pagado: 60000, saldo: 30000 }));
    await estable();
    expect(dialogos().length).toBe(0);
    expect(texto()).toContain('Abono registrado a Alumno 2');
    expect(texto()).toContain('saldo $30.000');
  });

  it('la prórroga exige motivo y el error de la API se ve en el popup', async () => {
    await cargar(ADMIN);
    el().querySelector<HTMLButtonElement>('[aria-label="Conceder prórroga a Alumno 1"]')!.click();
    await estable();
    boton('Conceder', ultimoDialogo())!.click();
    await estable();
    expect(ultimoDialogo().querySelector('[role="alert"]')?.textContent).toContain('motivo');

    const fecha = ultimoDialogo().querySelector<HTMLInputElement>('[formcontrolname="nueva_fecha_limite"]')!;
    escribir(fecha, isoLocal(sumarDias(HOY, 40)));
    escribir(ultimoDialogo().querySelector('textarea')!, 'Paga con la prima de diciembre');
    boton('Conceder', ultimoDialogo())!.click();
    backend.expectOne(`${API}/inscripciones/1/prorroga`)
      .flush({ detail: 'La nueva fecha límite no puede estar en el pasado.' }, { status: 422, statusText: 'Unprocessable' });
    await estable();
    expect(ultimoDialogo().querySelector('[role="alert"]')?.textContent).toContain('no puede estar en el pasado');
  });

  it('solo el SuperAdmin anula abonos y confirma expulsiones', async () => {
    const conPago = insc('4', {
      estado: 'a_expulsar', monto_pagado: 90000, saldo: 0,
      pagos: [{ id: 'p1', fecha: isoLocal(HOY), monto: 90000, anula_id: null, anulado: false, motivo: null, registrado_por: null, creado_en: '' }],
    });
    await cargar(ADMIN, [conPago]);
    boton('En revisión')!.click();
    await estable();
    el().querySelector<HTMLButtonElement>('.fila .alumno')!.click();
    await estable();
    expect(boton('Confirmar expulsión', ultimoDialogo())).toBeUndefined();
    expect(boton('Devolver a activa', ultimoDialogo())).toBeDefined();
    expect(boton('Anular', ultimoDialogo())).toBeUndefined(); // además, en revisión no se anulan abonos
    TestBed.resetTestingModule();

    await cargar(SUPERADMIN, [conPago]);
    boton('En revisión')!.click();
    await estable();
    el().querySelector<HTMLButtonElement>('.fila .alumno')!.click();
    await estable();
    boton('Confirmar expulsión', ultimoDialogo())!.click();
    await estable();
    escribir(ultimoDialogo().querySelector('textarea')!, 'Mora de más de tres meses');
    boton('Confirmar expulsión', ultimoDialogo())!.click();
    const cambio = backend.expectOne(`${API}/inscripciones/4/estado`);
    expect(cambio.request.body).toEqual({ estado: 'expulsado', motivo: 'Mora de más de tres meses' });
    cambio.flush({ ...conPago, estado: 'expulsado' });
    await estable();
    expect(texto()).toContain('Alumno 4: expulsión confirmada.');
  });

  it('el SuperAdmin anula un abono con motivo', async () => {
    const conPago = insc('2', {
      monto_pagado: 40000, saldo: 50000,
      pagos: [{ id: 'p1', fecha: isoLocal(HOY), monto: 40000, anula_id: null, anulado: false, motivo: null, registrado_por: null, creado_en: '' }],
    });
    await cargar(SUPERADMIN, [conPago]);
    el().querySelector<HTMLButtonElement>('.fila .alumno')!.click();
    await estable();
    boton('Anular', ultimoDialogo())!.click();
    await estable();
    escribir(ultimoDialogo().querySelector('textarea')!, 'Se registró dos veces');
    boton('Anular abono', ultimoDialogo())!.click();
    const anular = backend.expectOne(`${API}/inscripciones/2/pagos/p1/anular`);
    expect(anular.request.body).toEqual({ motivo: 'Se registró dos veces' });
    anular.flush({ ...conPago, monto_pagado: 0, saldo: 90000, pagos: [{ ...conPago.pagos[0]!, anulado: true }] });
    await estable();
    expect(texto()).toContain('Abono anulado');
  });

  it('la familia ve sus inscripciones sin indicadores ni acciones', async () => {
    await cargar(FAMILIA, [insc('1', { estado: 'activo', monto_pagado: 90000, saldo: 0 })]);
    expect(el().querySelector('.kpis')).toBeNull();
    expect(nombres()).toEqual(['Alumno 1']);
    expect(el().querySelector('.acciones-fila button')).toBeNull();
    expect(boton('how_to_reg Renovar')).toBeUndefined();
  });

  it('nueva inscripción: busca al alumno, no deja elegir a quien ya está inscrito y paga completo', async () => {
    await cargar(ADMIN, []);
    boton('how_to_reg Renovar alumno existente')!.click();
    await estable();
    escribir(ultimoDialogo().querySelector<HTMLInputElement>('input[type="search"]')!, 'Laura');
    await new Promise((r) => setTimeout(r, 350));
    const busqueda = backend.expectOne((r) => r.url === `${API}/alumnos`);
    expect(busqueda.request.params.get('buscar')).toBe('Laura');
    busqueda.flush([
      { id: 'a1', nombres: 'Laura', apellidos: 'Pérez', rama: 'femenina', inscripcion_estado: null },
      { id: 'a2', nombres: 'Laura', apellidos: 'Ríos', rama: 'femenina', inscripcion_estado: 'activo' },
    ]);
    await estable();
    const [libre, inscrita] = [...ultimoDialogo().querySelectorAll<HTMLButtonElement>('.candidato')];
    expect(inscrita!.disabled).toBe(true);
    libre!.click();
    ultimoDialogo().querySelector<HTMLInputElement>('input[value="completo"]')!.click();
    await estable();
    boton('Inscribir', ultimoDialogo())!.click();
    backend.expectOne((r) => r.method === 'POST' && r.url === `${API}/inscripciones`).flush(insc('9'));
    backend.expectOne(`${API}/inscripciones/9/pagos`).flush(insc('9', { estado: 'activo', monto_pagado: 90000, saldo: 0 }));
    pedirLista().flush([]);
    await estable();
    expect(texto()).toContain('quedó inscrito. La inscripción quedó paga y activa.');
  });
});
