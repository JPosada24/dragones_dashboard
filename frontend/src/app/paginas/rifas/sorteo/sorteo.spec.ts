import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { registerLocaleData } from '@angular/common';
import localeEsCo from '@angular/common/locales/es-CO';
import { LOCALE_ID } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { vi } from 'vitest';

import { isoLocal, sumarDias } from '../../../compartido/fechas';
import { AuthService } from '../../../core/auth/auth.service';
import { API, Usuario } from '../../../core/modelos';
import { Acta, Rifa, Talonario } from '../rifas.modelos';
import { SorteoPage, numeroWhatsApp } from './sorteo';

registerLocaleData(localeEsCo);

const HOY = new Date();
const ANIO = HOY.getFullYear();
const SUPERADMIN = ['alumnos.ver_todos', 'rifas.gestionar', 'pagos.registrar', 'pagos.anular', 'sorteo.jugar'];
const ADMIN = ['alumnos.ver_todos', 'rifas.gestionar', 'pagos.registrar'];

const rifa = (id: string, extra: Partial<Rifa> = {}): Rifa => ({
  id, nombre: `Rifa ${id}`, anio: ANIO, numero: Number(id), premio: 'Televisor', fecha_sorteo: isoLocal(HOY),
  puestos_por_talonario: 20, precio_puesto: 2000, valor_talonario: 40000, estado: 'abierta', motivo_cancelacion: null,
  talonarios: 2, talonarios_pagados: 1, recaudado: 50000, esperado: 80000, ...extra,
});

const talonario = (codigo: string, pagado: boolean, rama = 'femenina'): Talonario => ({
  id: `t-${codigo}`, alumno_id: `a-${codigo}`, alumno_nombre: `Alumno ${codigo}`, rama, codigo, boletas: 20,
  recaudado: pagado ? 40000 : 10000, saldo: pagado ? 0 : 30000, pagado, pagos: [],
});

const TALONARIOS = [talonario('M001', false, 'masculina'), talonario('F001', true)];
const acta = (orden: number, boleta: number): Acta => ({
  id: `acta-${orden}`, rifa_id: '1', orden, codigo: 'F001', boleta, alumno_id: 'a-F001', alumno_nombre: 'Laura Pérez',
  rama: 'femenina', total_participantes: 21 - orden, participantes: [], huella: 'a'.repeat(64), jugado_en: new Date().toISOString(),
});
const GANADORA = {
  id: 'a-F001', codigo: 'F001', nombres: 'Laura', apellidos: 'Pérez', telefono: null,
  acudientes: [{ acudiente_id: 'ac1', nombres: 'Marta', apellidos: 'Gómez', telefono: '300 123 4567', parentesco: 'madre', principal: true }],
};

describe('SorteoPage', () => {
  let backend: HttpTestingController;
  let fixture: ComponentFixture<SorteoPage>;

  async function cargar(permisos: string[], rifas: Rifa[]) {
    TestBed.configureTestingModule({
      imports: [SorteoPage],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting(), { provide: LOCALE_ID, useValue: 'es-CO' }],
    });
    const usuario: Usuario = { id: 'u', email: 'x@club.com', nombre: 'X', rol: 'ADMIN', activo: true, rama: null, permisos };
    TestBed.inject(AuthService).usuario.set(usuario);
    backend = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(SorteoPage);
    fixture.detectChanges();
    backend.expectOne((r) => r.url === `${API}/rifas` && r.params.get('anio') === String(ANIO)).flush(rifas);
    await estable();
  }

  afterEach(() => {
    backend.verify();
    vi.unstubAllGlobals();
  });

  const el = () => fixture.nativeElement as HTMLElement;
  const texto = () => el().textContent ?? '';
  const boton = (t: string, dentro: ParentNode = el()) =>
    [...dentro.querySelectorAll('button')].find((b) => b.textContent?.replace(/\s+/g, ' ').trim().startsWith(t)) as HTMLButtonElement | undefined;
  async function estable() {
    await fixture.whenStable();
    fixture.detectChanges();
  }

  it('elige la rifa que toca jugar y muestra la urna, los talonarios por código y el avance por rama', async () => {
    await cargar(SUPERADMIN, [rifa('1', { fecha_sorteo: isoLocal(sumarDias(HOY, 20)) }), rifa('2')]);
    backend.expectOne(`${API}/rifas/2/talonarios`).flush(TALONARIOS);
    await estable();
    expect(el().querySelector('.filtro[aria-pressed="true"]')?.textContent).toContain('Rifa 2'); // ya en fecha
    expect(el().querySelector('.en-urna')?.textContent).toContain('20');
    expect([...el().querySelectorAll('.talonario .codigo')].map((c) => c.textContent?.trim())).toEqual(['F001', 'M001']);
    boton('Sin pagar')!.click();
    await estable();
    expect([...el().querySelectorAll('.talonario .codigo')].map((c) => c.textContent?.trim())).toEqual(['M001']);
    expect(el().querySelectorAll('.rama').length).toBe(2);
  });

  it('juega (con confirmación), muestra la boleta F001-07 que eligió el servidor y avisa al acudiente', async () => {
    vi.stubGlobal('matchMedia', () => ({ matches: true })); // sin animación en la prueba
    await cargar(SUPERADMIN, [rifa('1')]);
    backend.expectOne(`${API}/rifas/1/talonarios`).flush(TALONARIOS);
    await estable();
    boton('casino Jugar la rifa')!.click();
    await estable();
    boton('casino Jugar ahora', el().querySelector('dialog')!)!.click();
    backend.expectOne((r) => r.method === 'POST' && r.url === `${API}/rifas/1/sorteo`).flush(acta(1, 7));
    await new Promise((r) => setTimeout(r, 0));
    backend.expectOne(`${API}/alumnos/a-F001`).flush(GANADORA);
    backend.expectOne(`${API}/rifas/1`).flush(rifa('1', { estado: 'sorteada' }));
    backend.expectOne(`${API}/rifas/1/actas`).flush([acta(1, 7)]); // historial
    await estable();
    expect([...el().querySelectorAll('.pantalla-valor')].map((v) => v.textContent?.trim())).toEqual(['F001', '07']);
    expect(el().querySelector('.ganador-nombre')?.textContent).toContain('Laura Pérez');
    const whatsapp = el().querySelector<HTMLAnchorElement>('a[href^="https://wa.me/"]')!;
    expect(whatsapp.href).toContain('https://wa.me/573001234567?text=');
    expect(decodeURIComponent(whatsapp.href)).toContain('¡Hola, Marta!');
    expect(decodeURIComponent(whatsapp.href)).toContain('la boleta número 07 del talonario de Laura ganó «Televisor»');
    expect(decodeURIComponent(whatsapp.href)).not.toContain('F001');
    // Se puede volver a jugar: la urna ya no cuenta la boleta que ganó.
    expect(boton('casino Jugar otra vez')!.disabled).toBe(false);
    expect(el().querySelector('.en-urna')?.textContent).toContain('19');
  });

  it('una rifa ya sorteada muestra sus jugadas; sin "sorteo.jugar" no aparece el botón', async () => {
    await cargar(ADMIN, [rifa('1', { estado: 'sorteada' })]);
    backend.expectOne(`${API}/rifas/1/talonarios`).flush(TALONARIOS);
    backend.match(`${API}/rifas/1/actas`).forEach((r) => r.flush([acta(1, 7), acta(2, 12)])); // escenario e historial
    await estable();
    backend.expectOne(`${API}/alumnos/a-F001`).flush(GANADORA);
    await estable();
    expect(boton('casino Jugar')).toBeUndefined();
    expect(el().querySelector('.ganador')?.textContent).toContain('2.ª jugada · boleta ganadora F001-12');
    expect(el().querySelectorAll('.jugadas li').length).toBe(2);
    expect(el().querySelectorAll('.historial').length).toBe(2);
  });

  it('antes de la fecha el botón está deshabilitado', async () => {
    await cargar(SUPERADMIN, [rifa('1', { fecha_sorteo: isoLocal(sumarDias(HOY, 3)) })]);
    backend.expectOne(`${API}/rifas/1/talonarios`).flush(TALONARIOS);
    await estable();
    expect(boton('casino Jugar la rifa')!.disabled).toBe(true);
    expect(texto()).toContain('Ese día se habilita');
  });
});

describe('numeroWhatsApp', () => {
  it('normaliza celulares colombianos y descarta lo que no es un número', () => {
    expect(numeroWhatsApp('300 123 4567')).toBe('573001234567');
    expect(numeroWhatsApp('+57 300-123-4567')).toBe('573001234567');
    expect(numeroWhatsApp('6041234')).toBeNull();
    expect(numeroWhatsApp(null)).toBeNull();
    expect(numeroWhatsApp('javascript:alert(1)')).toBeNull();
  });
});
