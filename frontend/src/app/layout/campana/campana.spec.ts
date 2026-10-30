import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { registerLocaleData } from '@angular/common';
import localeEsCo from '@angular/common/locales/es-CO';
import { LOCALE_ID } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { API, Notificacion } from '../../core/modelos';
import { NotificacionesService } from '../../core/notificaciones.service';
import { Campana } from './campana';

registerLocaleData(localeEsCo);

const aviso = (id: string, leida = false): Notificacion => ({
  id, tipo: 'multa', titulo: `Aviso ${id}`, mensaje: '<b>texto</b>', alumno_id: null, leida, creado_en: '2026-10-29T10:00:00-05:00',
});

describe('Campana de avisos', () => {
  let backend: HttpTestingController;
  let fixture: ComponentFixture<Campana>;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [Campana],
      providers: [provideHttpClient(), provideHttpClientTesting(), { provide: LOCALE_ID, useValue: 'es-CO' }],
    });
    backend = TestBed.inject(HttpTestingController);
    TestBed.inject(NotificacionesService).noLeidas.set(2);
    fixture = TestBed.createComponent(Campana);
    fixture.detectChanges();
  });

  afterEach(() => backend.verify());

  const el = () => fixture.nativeElement as HTMLElement;
  const disparador = () => el().querySelector<HTMLButtonElement>('.disparador')!;
  async function estable() {
    await fixture.whenStable();
    fixture.detectChanges();
  }

  it('muestra el conteo y despliega los avisos sin cambiar de página', async () => {
    expect(disparador().getAttribute('aria-label')).toBe('Avisos: 2 sin leer');
    expect(el().querySelector('.desplegable')).toBeNull();
    disparador().click();
    await estable();
    backend.expectOne((r) => r.url === `${API}/notificaciones/mias`).flush([aviso('1'), aviso('2'), aviso('3', true)]);
    await estable();
    expect(disparador().getAttribute('aria-expanded')).toBe('true');
    expect(el().querySelectorAll('.aviso').length).toBe(3);
    expect(el().querySelector('.aviso p')?.textContent).toBe('<b>texto</b>'); // texto, nunca HTML
  });

  it('marca todo como leído y se cierra con Escape o con un clic fuera', async () => {
    disparador().click();
    await estable();
    backend.expectOne((r) => r.url === `${API}/notificaciones/mias`).flush([aviso('1'), aviso('2')]);
    await estable();
    [...el().querySelectorAll('button')].find((b) => b.textContent?.includes('Marcar todo'))!.click();
    backend.expectOne(`${API}/notificaciones/mias/leer-todas`).flush({ marcadas: 2 });
    await estable();
    expect(el().querySelector('.conteo')).toBeNull();

    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }));
    await estable();
    expect(el().querySelector('.desplegable')).toBeNull();

    disparador().click();
    await estable();
    backend.expectOne((r) => r.url === `${API}/notificaciones/mias`).flush([]);
    await estable();
    document.body.click();
    await estable();
    expect(el().querySelector('.desplegable')).toBeNull();
  });
});
