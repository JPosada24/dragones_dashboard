import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, TestRequest, provideHttpClientTesting } from '@angular/common/http/testing';
import { registerLocaleData } from '@angular/common';
import localeEsCo from '@angular/common/locales/es-CO';
import { LOCALE_ID } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { AuthService } from '../../core/auth/auth.service';
import { API, Usuario } from '../../core/modelos';
import { AlumnosPage } from './alumnos';
import { Alumno, EstadoCuenta } from './alumnos.modelos';

registerLocaleData(localeEsCo);

const ADMIN = ['alumnos.ver_todos', 'alumnos.editar'];
const ENTRENADOR = ['alumnos.ver_rama', 'alumnos.editar'];
const FAMILIA = ['alumnos.ver_propios'];
const INSCRIBE = [...ADMIN, 'inscripciones.crear', 'inscripciones.abonar'];

const inscripcion = (extra: Record<string, unknown> = {}) => ({
  id: 'i1', valor: 90000, monto_pagado: null, saldo: 90000, estado: 'pendiente_pago', fecha_limite_pago: '2026-11-29',
  ...extra,
});

const alumno = (id: string, extra: Partial<Alumno> = {}): Alumno => ({
  id, codigo: 'F001', nombres: 'Laura', apellidos: 'Pérez', tipo_documento: 'TI', documento: '****4321', fecha_nacimiento: '2013-05-04',
  edad: 13, es_menor: true, rama: 'femenina', telefono: null, email: null, direccion: null, eps: 'Sura',
  usuario_id: null, activo: true, inscripcion_estado: 'activo',
  acudientes: [{ acudiente_id: 'ac1', nombres: 'Marta', apellidos: 'Gómez', telefono: '3001234567', parentesco: 'madre', principal: true }],
  ...extra,
});

const CUENTA: EstadoCuenta = {
  alumno_id: 'a1', inscripcion_estado: 'activo', inscripcion_saldo: 0, multas_pendientes: 1, multas_saldo: 2000,
  rifas: [], total: 2000, al_dia: false, en_mora: false, entra_en_mora: '2027-01-15',
};

describe('AlumnosPage', () => {
  let backend: HttpTestingController;
  let fixture: ComponentFixture<AlumnosPage>;

  function crear(permisos: string[], rama: 'femenina' | null = null) {
    TestBed.configureTestingModule({
      imports: [AlumnosPage],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting(), { provide: LOCALE_ID, useValue: 'es-CO' }],
    });
    const usuario: Usuario = { id: 'u', email: 'x@club.com', nombre: 'X', rol: 'ADMIN', activo: true, rama, permisos };
    TestBed.inject(AuthService).usuario.set(usuario);
    backend = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(AlumnosPage);
    fixture.detectChanges();
  }

  afterEach(() => backend.verify());

  const el = () => fixture.nativeElement as HTMLElement;
  const texto = () => el().textContent ?? '';
  const boton = (t: string, dentro: ParentNode = el()) =>
    [...dentro.querySelectorAll('button')].find((b) => b.textContent?.trim() === t) as HTMLButtonElement | undefined;
  const dialogo = () => el().querySelector('dialog')!;
  const pedirLista = (): TestRequest => backend.expectOne((r) => r.url === `${API}/alumnos`);
  async function estable() {
    await fixture.whenStable();
    fixture.detectChanges();
  }
  function escribir(selector: string, valor: string) {
    const campo = el().querySelector<HTMLInputElement | HTMLSelectElement>(selector)!;
    campo.value = valor;
    campo.dispatchEvent(new Event(campo instanceof HTMLSelectElement ? 'change' : 'input'));
  }
  function responderFicha(a: Alumno, inscripciones: unknown[] = []) {
    backend.expectOne((r) => r.url === `${API}/inscripciones` && r.params.get('alumno_id') === a.id).flush(inscripciones);
    backend.expectOne(`${API}/alumnos/${a.id}`).flush(a);
    backend.expectOne(`${API}/alumnos/${a.id}/estado-cuenta`).flush(CUENTA);
    backend.expectOne(`${API}/alumnos/${a.id}/asistencia`).flush([
      { sesion_id: 's1', fecha: '2026-10-28', hora_inicio: '18:00:00', estado: 'ausente', multa_valor: 2000, multa_estado: 'pendiente' },
      { sesion_id: 's2', fecha: '2026-10-26', hora_inicio: '18:00:00', estado: 'presente', multa_valor: null, multa_estado: null },
    ]);
    backend.expectOne(`${API}/alumnos/${a.id}/documentos`).flush([
      { id: 'd1', tipo: 'eps', nombre_original: 'eps.pdf', mime: 'application/pdf', tamano: 2048, creado_en: '2026-10-01T10:00:00-05:00' },
    ]);
  }

  it('el staff filtra la lista y abre la ficha completa del alumno', async () => {
    crear(ADMIN);
    const lista = pedirLista();
    expect(lista.request.params.get('activo')).toBe('true');
    lista.flush([alumno('a1'), alumno('a2', { nombres: 'Sara', inscripcion_estado: null })]);
    await estable();
    expect(el().querySelectorAll('.item').length).toBe(2);

    boton('Masculina')!.click();
    expect(pedirLista().request.params.get('rama')).toBe('masculina');

    (el().querySelector('.item') as HTMLButtonElement).click();
    responderFicha(alumno('a1'));
    await estable();
    expect(el().querySelector('.nombre')?.textContent).toContain('Laura Pérez');
    expect(texto()).toContain('****4321');
    expect(texto()).toContain('Marta Gómez');
    expect(texto()).toContain('asistió 1/2');
    expect(texto()).toContain('multa $2.000 · pendiente');
    expect(texto()).toContain('Certificado de EPS');
    expect(texto()).toContain('Con saldo');
  });

  it('el documento completo solo se pide al presionar "Ver completo"', async () => {
    crear(ADMIN);
    pedirLista().flush([alumno('a1')]);
    await estable();
    (el().querySelector('.item') as HTMLButtonElement).click();
    responderFicha(alumno('a1'));
    await estable();
    boton('Ver completo')!.click();
    backend.expectOne(`${API}/alumnos/a1/documento-identidad`).flush({ tipo_documento: 'TI', documento: '1098765432' });
    await estable();
    expect(texto()).toContain('1098765432');
    boton('Ocultar')!.click();
    await estable();
    expect(texto()).not.toContain('1098765432');
  });

  it('el entrenador no filtra por rama ni ve el documento completo', async () => {
    crear(ENTRENADOR, 'femenina');
    pedirLista().flush([alumno('a1')]);
    await estable();
    expect(boton('Masculina')).toBeUndefined();
    (el().querySelector('.item') as HTMLButtonElement).click();
    responderFicha(alumno('a1'));
    await estable();
    expect(boton('Ver completo')).toBeUndefined();
    expect(boton('edit Editar')).toBeDefined();
  });

  it('la familia con un hijo lo ve directo y sin botones de edición', async () => {
    crear(FAMILIA);
    const lista = pedirLista();
    expect(lista.request.params.has('activo')).toBe(false);
    lista.flush([alumno('a1')]);
    responderFicha(alumno('a1'));
    await estable();
    expect(el().querySelector('#buscar-alumno')).toBeNull();
    expect(el().querySelector('.nombre')?.textContent).toContain('Laura Pérez');
    expect(boton('edit Editar')).toBeUndefined();
    expect(boton('upload Subir')).toBeUndefined();
    expect(boton('add Agregar')).toBeUndefined();
    expect(el().querySelector('[aria-label^="Descargar"]')).not.toBeNull();
  });

  it('busca por texto con una pequeña espera', async () => {
    crear(ADMIN);
    pedirLista().flush([]);
    await estable();
    escribir('#buscar-alumno', 'Pér');
    backend.expectNone((r) => r.url === `${API}/alumnos`);
    await new Promise((r) => setTimeout(r, 350));
    expect(pedirLista().request.params.get('buscar')).toBe('Pér');
  });

  it('registra un alumno menor con un acudiente nuevo sin duplicarlo al reintentar', async () => {
    crear(ADMIN);
    pedirLista().flush([]);
    await estable();
    (el().querySelector('[aria-label="Nuevo alumno"]') as HTMLButtonElement).click();
    await estable();
    escribir('dialog [formcontrolname="nombres"]', 'Laura');
    escribir('dialog [formcontrolname="apellidos"]', 'Pérez');
    escribir('dialog [formcontrolname="documento"]', '1098765432');
    escribir('dialog [formcontrolname="fecha_nacimiento"]', '2013-05-04');
    escribir('dialog [formcontrolname="tipo_documento"]', 'TI'); // los selects empiezan en «Selecciona…»
    escribir('dialog [formcontrolname="rama"]', 'femenina');

    // Acudiente: se busca por documento; no existe, así que se piden sus datos.
    const tipoAcudiente = dialogo().querySelectorAll<HTMLSelectElement>('[formcontrolname="tipo_documento"]')[1]!;
    tipoAcudiente.value = 'CC';
    tipoAcudiente.dispatchEvent(new Event('change'));
    const docAcudiente = dialogo().querySelectorAll<HTMLInputElement>('[formcontrolname="documento"]')[1]!;
    docAcudiente.value = '43111222';
    docAcudiente.dispatchEvent(new Event('input'));
    boton('Buscar', dialogo())!.click();
    const busqueda = backend.expectOne((r) => r.url === `${API}/acudientes`);
    expect(busqueda.request.params.get('documento')).toBe('43111222');
    busqueda.flush([]);
    await estable();
    escribir('dialog [formcontrolname="parentesco"]', 'madre');
    const [, nombresAcu] = dialogo().querySelectorAll<HTMLInputElement>('[formcontrolname="nombres"]');
    const [, apellidosAcu] = dialogo().querySelectorAll<HTMLInputElement>('[formcontrolname="apellidos"]');
    for (const [campo, valor] of [[nombresAcu!, 'Marta'], [apellidosAcu!, 'Gómez']] as const) {
      campo.value = valor;
      campo.dispatchEvent(new Event('input'));
    }
    escribir('dialog fieldset [formcontrolname="telefono"]', '3001234567');
    await estable();

    boton('Registrar alumno', dialogo())!.click();
    const nuevoAcudiente = backend.expectOne((r) => r.method === 'POST' && r.url === `${API}/acudientes`);
    expect(nuevoAcudiente.request.body).toMatchObject({ nombres: 'Marta', documento: '43111222', telefono: '3001234567' });
    nuevoAcudiente.flush({ id: 'ac9', nombres: 'Marta', apellidos: 'Gómez', tipo_documento: 'CC', documento: '****1222', telefono: '3001234567', email: null });
    const alta = backend.expectOne((r) => r.method === 'POST' && r.url === `${API}/alumnos`);
    expect(alta.request.body.acudientes).toEqual([{ acudiente_id: 'ac9', parentesco: 'madre', principal: false }]);
    alta.flush({ detail: 'Ya existe un alumno con ese documento.' }, { status: 409, statusText: 'Conflict' });
    await estable();
    expect(dialogo().querySelector('[role="alert"]')?.textContent).toContain('Ya existe un alumno');

    // Al reintentar ya no crea otro acudiente: reutiliza el que se registró.
    boton('Registrar alumno', dialogo())!.click();
    backend.expectNone((r) => r.method === 'POST' && r.url === `${API}/acudientes`);
    const reintento = backend.expectOne((r) => r.method === 'POST' && r.url === `${API}/alumnos`);
    expect(reintento.request.body.acudientes[0].acudiente_id).toBe('ac9');
    reintento.flush(alumno('a7'));
    pedirLista().flush([alumno('a7')]);
    responderFicha(alumno('a7'));
    await estable();
    expect(el().querySelector('dialog')).toBeNull();
    expect(texto()).toContain('quedó registrado');
  });

  it('inscribe a un alumno nuevo en un solo paso: ficha, inscripción y abono', async () => {
    crear(INSCRIBE);
    pedirLista().flush([]);
    await estable();
    (el().querySelector('[aria-label="Inscribir alumno nuevo"]') as HTMLButtonElement).click();
    await estable();
    expect(dialogo().querySelector('input[formcontrolname="inscribir"]')).toBeNull(); // ya no es opcional
    escribir('dialog [formcontrolname="nombres"]', 'Sara');
    escribir('dialog [formcontrolname="apellidos"]', 'Ríos');
    escribir('dialog [formcontrolname="documento"]', '1012345678');
    escribir('dialog [formcontrolname="fecha_nacimiento"]', '2000-01-01');
    escribir('dialog [formcontrolname="tipo_documento"]', 'CC');
    escribir('dialog [formcontrolname="rama"]', 'femenina');
    (dialogo().querySelector('input[type="radio"][value="parcial"]') as HTMLInputElement).click();
    await estable();
    escribir('dialog [formcontrolname="monto"]', '40000');
    await estable();

    boton('Inscribir alumno', dialogo())!.click();
    backend.expectNone((r) => r.method === 'POST' && r.url === `${API}/alumnos`);
    const alta = backend.expectOne(`${API}/inscripciones/alumno-nuevo`);
    expect(alta.request.body.alumno).toMatchObject({ nombres: 'Sara', documento: '1012345678', acudientes: [] });
    expect(alta.request.body.pago).toEqual({ forma: 'parcial', monto: 40000 });
    alta.flush(inscripcion({ alumno_id: 'a8', alumno_nombre: 'Sara Ríos', monto_pagado: 40000, saldo: 50000 }));
    pedirLista().flush([]);
    responderFicha(alumno('a8'));
    await estable();
    expect(texto()).toContain('Sara Ríos quedó inscrito');
    expect(texto()).toContain('Abonó $40.000; saldo $50.000 hasta el 29/11/2026');
  });

  it('la ficha muestra la inscripción del año y registra un abono ahí mismo', async () => {
    crear(INSCRIBE);
    pedirLista().flush([alumno('a1', { inscripcion_estado: 'pendiente_pago' })]);
    await estable();
    (el().querySelector('.item') as HTMLButtonElement).click();
    responderFicha(alumno('a1', { inscripcion_estado: 'pendiente_pago' }), [inscripcion({ monto_pagado: 40000, saldo: 50000 })]);
    await estable();
    const tarjeta = el().querySelector('.tarjeta-inscripcion')!;
    expect(tarjeta.textContent).toContain('$40.000 de $90.000');
    expect(tarjeta.textContent).toContain('Saldo $50.000');
    expect(tarjeta.querySelector('a')?.getAttribute('href')).toContain('/alumnos/inscripciones?id=i1');

    boton('payments Registrar abono', tarjeta)!.click();
    await estable();
    expect(dialogo().querySelector<HTMLInputElement>('[formcontrolname="monto"]')!.value).toBe(''); // sin valor por defecto
    boton('Usar el saldo completo ($50.000)', dialogo())!.click();
    await estable();
    boton('Registrar', dialogo())!.click();
    const pago = backend.expectOne(`${API}/inscripciones/i1/pagos`);
    expect(pago.request.body.monto).toBe(50000);
    pago.flush(inscripcion({ alumno_id: 'a1', monto_pagado: 90000, saldo: 0, estado: 'activo' }));
    responderFicha(alumno('a1'));
    pedirLista().flush([alumno('a1')]);
    await estable();
    expect(texto()).toContain('quedó paga y activa');
  });

  it('renueva desde la ficha a quien no tiene inscripción este año, con pago completo', async () => {
    crear(INSCRIBE);
    pedirLista().flush([alumno('a1', { inscripcion_estado: null })]);
    await estable();
    (el().querySelector('.item') as HTMLButtonElement).click();
    responderFicha(alumno('a1', { inscripcion_estado: null }));
    await estable();
    boton(`how_to_reg Renovar inscripción ${new Date().getFullYear()}`)!.click();
    await estable();
    (dialogo().querySelector('input[type="radio"][value="completo"]') as HTMLInputElement).click();
    await estable();
    boton('Inscribir', dialogo())!.click();
    backend.expectOne((r) => r.method === 'POST' && r.url === `${API}/inscripciones`).flush(inscripcion());
    const pago = backend.expectOne(`${API}/inscripciones/i1/pagos`);
    expect(pago.request.body.monto).toBe(90000); // el saldo que informó el servidor
    pago.flush(inscripcion({ monto_pagado: 90000, saldo: 0, estado: 'activo' }));
    responderFicha(alumno('a1'));
    pedirLista().flush([alumno('a1')]);
    await estable();
    expect(texto()).toContain('quedó paga y activa');
  });

  it('sin permiso de inscribir no aparece la opción', async () => {
    crear(ADMIN);
    pedirLista().flush([alumno('a1', { inscripcion_estado: null })]);
    await estable();
    (el().querySelector('.item') as HTMLButtonElement).click();
    responderFicha(alumno('a1', { inscripcion_estado: null }));
    await estable();
    expect(texto()).not.toContain('Renovar inscripción');
    expect(el().querySelector('[aria-label="Nuevo alumno"]')).not.toBeNull();
  });

  it('el SuperAdmin elimina un alumno solo después de escribir su código', async () => {
    crear([...ADMIN, 'alumnos.eliminar']);
    pedirLista().flush([alumno('a1')]);
    await estable();
    (el().querySelector('.item') as HTMLButtonElement).click();
    responderFicha(alumno('a1'));
    await estable();
    (el().querySelector('[aria-label="Eliminar alumno"]') as HTMLButtonElement).click();
    await estable();
    expect(dialogo().querySelector('.advertencia')?.textContent).toContain('Se perderá toda la información');
    const eliminar = boton('Eliminar definitivamente', dialogo())!;
    expect(eliminar.disabled).toBe(true);
    escribir('dialog input.mono', 'f001');
    await estable();
    expect(eliminar.disabled).toBe(false);
    eliminar.click();
    backend.expectOne((r) => r.method === 'DELETE' && r.url === `${API}/alumnos/a1`).flush(null, { status: 204, statusText: 'No Content' });
    await estable();
    expect(texto()).toContain('fue eliminado con toda su información');
    expect(el().querySelectorAll('.item').length).toBe(0);
  });

  it('sin el permiso no aparece la opción de eliminar', async () => {
    crear(ADMIN);
    pedirLista().flush([alumno('a1')]);
    await estable();
    (el().querySelector('.item') as HTMLButtonElement).click();
    responderFicha(alumno('a1'));
    await estable();
    expect(el().querySelector('[aria-label="Eliminar alumno"]')).toBeNull();
  });
});
