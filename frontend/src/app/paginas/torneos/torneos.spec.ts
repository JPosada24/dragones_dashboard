import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { registerLocaleData } from '@angular/common';
import localeEsCo from '@angular/common/locales/es-CO';
import { LOCALE_ID } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { isoLocal, sumarDias } from '../../compartido/fechas';
import { AuthService } from '../../core/auth/auth.service';
import { API, Usuario } from '../../core/modelos';
import { TorneosPage } from './torneos';
import { Equipo, Torneo } from './torneos.modelos';

registerLocaleData(localeEsCo);

const HOY = new Date();
const ADMIN = ['eventos.gestionar', 'pagos.registrar'];
const SUPERADMIN = [...ADMIN, 'pagos.anular'];

const torneo = (id: string, extra: Partial<Torneo> = {}): Torneo => ({
  id, nombre: `Copa ${id}`, rama: 'femenina', fecha_inicio: isoLocal(sumarDias(HOY, 20)), fecha_fin: isoLocal(sumarDias(HOY, 21)),
  fecha_limite_inscripcion: isoLocal(sumarDias(HOY, 10)), lugar: 'Coliseo', cupo_equipos: 2, valor_inscripcion: 150000,
  estado: 'programado', motivo_cancelacion: null, ocupados: 2, confirmados: 1, en_espera: 1, recaudado: 200000, ...extra,
});

const equipo = (id: string, extra: Partial<Equipo> = {}): Equipo => ({
  id, nombre_club: `Club ${id}`, ciudad: 'Medellín', delegado_nombre: 'Ana Ruiz', delegado_telefono: '3101234567',
  delegado_email: null, estado: 'pendiente_pago', valor: 150000, monto_pagado: 50000, saldo: 100000, motivo_retiro: null,
  pagos: [{ id: `p-${id}`, fecha: isoLocal(HOY), monto: 50000, anula_id: null, motivo: null, creado_en: '' }], ...extra,
});

describe('TorneosPage', () => {
  let backend: HttpTestingController;
  let fixture: ComponentFixture<TorneosPage>;

  async function cargar(permisos: string[], lista: Torneo[]) {
    TestBed.configureTestingModule({
      imports: [TorneosPage],
      providers: [provideHttpClient(), provideHttpClientTesting(), { provide: LOCALE_ID, useValue: 'es-CO' }],
    });
    const usuario: Usuario = { id: 'u', email: 'x@club.com', nombre: 'X', rol: 'ADMIN', activo: true, permisos };
    TestBed.inject(AuthService).usuario.set(usuario);
    backend = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(TorneosPage);
    fixture.detectChanges();
    backend.expectOne(`${API}/torneos`).flush(lista);
    await estable();
  }

  afterEach(() => backend.verify());

  const el = () => fixture.nativeElement as HTMLElement;
  const texto = () => el().textContent ?? '';
  const ultimo = () => [...el().querySelectorAll('dialog')].at(-1)!;
  const boton = (t: string, dentro: ParentNode = el()) =>
    [...dentro.querySelectorAll('button')].find((b) => b.textContent?.replace(/\s+/g, ' ').trim().startsWith(t)) as HTMLButtonElement | undefined;
  async function estable() {
    await fixture.whenStable();
    fixture.detectChanges();
  }
  function escribir(selector: string, valor: string) {
    const c = ultimo().querySelector<HTMLInputElement | HTMLSelectElement>(selector)!;
    c.value = valor;
    c.dispatchEvent(new Event(c instanceof HTMLSelectElement ? 'change' : 'input'));
  }

  it('separa próximos, pasados y cancelados, con indicadores', async () => {
    await cargar(ADMIN, [
      torneo('1'),
      torneo('2', { fecha_inicio: isoLocal(sumarDias(HOY, -10)), fecha_fin: isoLocal(sumarDias(HOY, -9)) }),
      torneo('3', { estado: 'cancelado' }),
    ]);
    expect(el().querySelectorAll('.torneo').length).toBe(1);
    expect(el().querySelector('.kpis')!.textContent).toContain('$100.000'); // 2 cupos × 150.000 − 200.000 recaudado
    boton('Cancelados')!.click();
    await estable();
    expect(el().querySelector('.torneo h2')?.textContent).toContain('Copa 3');
  });

  it('crea un torneo: campos vacíos, cupo vacío = sugerido', async () => {
    await cargar(ADMIN, []);
    boton('add Nuevo torneo')!.click();
    await estable();
    expect(ultimo().querySelector<HTMLInputElement>('[formcontrolname="nombre"]')!.value).toBe('');
    escribir('[formcontrolname="nombre"]', 'Copa Dragones');
    escribir('[formcontrolname="rama"]', 'femenina');
    escribir('[formcontrolname="fecha_inicio"]', isoLocal(sumarDias(HOY, 30)));
    escribir('[formcontrolname="fecha_fin"]', isoLocal(sumarDias(HOY, 31)));
    escribir('[formcontrolname="fecha_limite_inscripcion"]', isoLocal(sumarDias(HOY, 20)));
    escribir('[formcontrolname="valor_inscripcion"]', '150000');
    await estable();
    boton('Crear torneo', ultimo())!.click();
    const r = backend.expectOne((x) => x.method === 'POST' && x.url === `${API}/torneos`);
    expect(r.request.body).toMatchObject({ nombre: 'Copa Dragones', rama: 'femenina', lugar: null, valor_inscripcion: 150000 });
    expect(r.request.body.cupo_equipos).toBeUndefined();
    r.flush(torneo('9', { nombre: 'Copa Dragones' }));
    backend.expectOne(`${API}/torneos`).flush([torneo('9')]);
    await estable();
    expect(texto()).toContain('se cancelan solos');
  });

  it('en los clubes registra pagos y retira; anular solo el SuperAdmin', async () => {
    await cargar(ADMIN, [torneo('1')]);
    boton('groups Clubes')!.click();
    await estable();
    backend.expectOne(`${API}/torneos/1/equipos`).flush([equipo('a'), equipo('b', { estado: 'en_espera', monto_pagado: 0, pagos: [] })]);
    await estable();
    expect(ultimo().querySelectorAll('.equipo').length).toBe(2);
    expect(ultimo().querySelector('a[href^="https://wa.me/573101234567"]')).not.toBeNull();
    expect(boton('Anular', ultimo())).toBeUndefined();

    boton('Registrar pago', ultimo())!.click();
    await estable();
    boton('Usar el saldo completo', ultimo())!.click();
    boton('Registrar', ultimo().querySelector('form')!)!.click();
    const pago = backend.expectOne(`${API}/torneos/1/equipos/a/pagos`);
    expect(pago.request.body).toEqual({ monto: 100000, fecha: isoLocal(HOY) });
    pago.flush(equipo('a', { estado: 'confirmado', monto_pagado: 150000, saldo: 0 }));
    backend.expectOne(`${API}/torneos/1/equipos`).flush([equipo('a', { estado: 'confirmado', saldo: 0 })]);
    backend.expectOne(`${API}/torneos/1`).flush(torneo('1'));
    await estable();
    expect(texto()).toContain('queda confirmado');
  });

  it('el SuperAdmin anula un pago sin motivo y eliminar pide confirmación', async () => {
    await cargar(SUPERADMIN, [torneo('1')]);
    boton('groups Clubes')!.click();
    await estable();
    backend.expectOne(`${API}/torneos/1/equipos`).flush([equipo('a')]);
    await estable();
    boton('Anular', ultimo())!.click();
    await estable();
    boton('Anular pago', ultimo())!.click();
    const r = backend.expectOne(`${API}/torneos/1/equipos/a/pagos/p-a/anular`);
    expect(r.request.body).toEqual({ motivo: null });
    r.flush(equipo('a', { monto_pagado: 0, saldo: 150000 }));
    backend.expectOne(`${API}/torneos/1/equipos`).flush([equipo('a')]);
    backend.expectOne(`${API}/torneos/1`).flush(torneo('1'));
    await estable();
    expect(texto()).toContain('Pago anulado');
  });

  it('eliminar un torneo', async () => {
    await cargar(ADMIN, [torneo('1', { recaudado: 0 })]);
    el().querySelector<HTMLButtonElement>('[aria-label="Eliminar Copa 1"]')!.click();
    await estable();
    boton('Eliminar torneo', ultimo())!.click();
    backend.expectOne((x) => x.method === 'DELETE' && x.url === `${API}/torneos/1`).flush(null, { status: 204, statusText: 'No Content' });
    backend.expectOne(`${API}/torneos`).flush([]);
    await estable();
    expect(texto()).toContain('«Copa 1» eliminado');
  });
});
