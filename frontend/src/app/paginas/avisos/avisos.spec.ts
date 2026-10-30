import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { registerLocaleData } from '@angular/common';
import localeEsCo from '@angular/common/locales/es-CO';
import { LOCALE_ID } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { API } from '../../core/modelos';
import { AvisosPage } from './avisos';

registerLocaleData(localeEsCo);

const AVISO = {
  id: 'n1', tipo: 'multa', titulo: 'Multa de Laura', telefono: '3001234567', mensaje: '<b>Hola</b> Marta',
  enlace: 'https://wa.me/573001234567?text=Hola', creado_en: new Date().toISOString(),
};

describe('AvisosPage', () => {
  let backend: HttpTestingController;
  let fixture: ComponentFixture<AvisosPage>;

  beforeEach(async () => {
    TestBed.configureTestingModule({
      imports: [AvisosPage],
      providers: [provideHttpClient(), provideHttpClientTesting(), { provide: LOCALE_ID, useValue: 'es-CO' }],
    });
    backend = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(AvisosPage);
    fixture.detectChanges();
  });

  afterEach(() => backend.verify());

  const el = () => fixture.nativeElement as HTMLElement;
  const boton = (t: string) => [...el().querySelectorAll('button')].find((b) => b.textContent?.trim().startsWith(t));
  async function estable() {
    await fixture.whenStable();
    fixture.detectChanges();
  }

  it('lista los WhatsApp por enviar: el mensaje es texto y tras abrirlo se marca enviado', async () => {
    backend.expectOne(`${API}/notificaciones/whatsapp`).flush([AVISO]);
    await estable();
    expect(el().querySelector('.aviso-mensaje')?.textContent).toBe('<b>Hola</b> Marta'); // nunca HTML
    expect(el().textContent).toContain('Multa');
    const enlace = el().querySelector<HTMLAnchorElement>('a[href^="https://wa.me/"]')!;
    expect(boton('Sí, enviado')).toBeUndefined();
    enlace.addEventListener('click', (e) => e.preventDefault()); // no abrir una pestaña en la prueba
    enlace.click();
    await estable();
    boton('Sí, enviado')!.click();
    const r = backend.expectOne(`${API}/notificaciones/n1/whatsapp`);
    expect(r.request.body).toEqual({ accion: 'enviado' });
    r.flush(null, { status: 204, statusText: 'No Content' });
    await estable();
    expect(el().querySelectorAll('.aviso').length).toBe(0);
  });

  it('no muestra un enlace que no sea de WhatsApp', async () => {
    backend.expectOne(`${API}/notificaciones/whatsapp`).flush([{ ...AVISO, enlace: 'javascript:alert(1)' }]);
    await estable();
    expect(el().querySelector('a[href]')).toBeNull();
    boton('Descartar')!.click();
    backend.expectOne(`${API}/notificaciones/n1/whatsapp`).flush(null, { status: 204, statusText: 'No Content' });
    await estable();
    expect(el().textContent).toContain('Aviso descartado');
  });

  it('muestra el estado de los correos y filtra por fallidos', async () => {
    backend.expectOne(`${API}/notificaciones/whatsapp`).flush([]);
    await estable();
    boton('Correos')!.click();
    backend.expectOne(`${API}/notificaciones/correos`).flush([
      { id: 'c1', tipo: 'multa', titulo: 'Multa', email: 'ma***@club.com', estado: 'fallido', intentos: 3, error: 'SMTP caído', creado_en: '' },
    ]);
    await estable();
    expect(el().textContent).toContain('Falló · 3 intentos');
    boton('Fallidos')!.click();
    expect(backend.expectOne((r) => r.url === `${API}/notificaciones/correos`).request.params.get('estado')).toBe('fallido');
  });
});
