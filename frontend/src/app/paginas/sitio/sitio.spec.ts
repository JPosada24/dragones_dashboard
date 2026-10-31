import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { API } from '../../core/modelos';
import { SitioPage } from './sitio';

const SITIO = {
  perfil: {
    nombre: 'Club Dragones', lema: 'Garra y corazón', ciudad: 'Manizales', sede: 'Coliseo', mision: '<b>Formar</b>',
    vision: null, historia: null, whatsapp: '3001234567', correo: 'contacto@club.com', instagram: 'dragones',
    facebook: null, publicado: true,
  },
  horario: [{ dia_semana: 0, hora_inicio: '18:00:00', hora_fin: '20:00:00', lugar: null }],
  albumes: [{ id: 'a1', nombre: 'Copa', fecha: null, publicado: true, fotos: [{ id: 'f1', ancho: 1920, alto: 1280 }] }],
  videos: [
    { id: 'v1', titulo: 'Resumen', youtube_id: 'dQw4w9WgXcQ', publicado: true },
    { id: 'v2', titulo: 'Malo', youtube_id: 'javascript:x', publicado: true },
  ],
  equipo: [{ id: 'i1', nombre: 'Ana Ruiz', cargo: 'Entrenadora', bio: null, orden: 0, publicado: true }],
  torneos: [{
    id: 't1', nombre: 'Copa Dragones', rama: 'femenina', fecha_inicio: '2026-11-22', fecha_fin: '2026-11-23',
    fecha_limite_inscripcion: '2026-11-17', lugar: 'Coliseo', valor_inscripcion: 150000, cupos_libres: 3,
  }],
};

describe('SitioPage', () => {
  let backend: HttpTestingController;
  let fixture: ComponentFixture<SitioPage>;

  async function cargar(respuesta: object | null, status = 200) {
    TestBed.configureTestingModule({
      imports: [SitioPage], providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    backend = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(SitioPage);
    fixture.detectChanges();
    backend.expectOne(`${API}/publico/club`).flush(respuesta, { status, statusText: status === 200 ? 'OK' : 'Error' });
    await estable();
  }

  afterEach(() => backend.verify());

  const el = () => fixture.nativeElement as HTMLElement;
  const boton = (t: string) => [...el().querySelectorAll('button')].find((b) => b.textContent?.trim().startsWith(t));
  async function estable() {
    await fixture.whenStable();
    fixture.detectChanges();
  }
  function escribir(nombre: string, valor: string) {
    const c = el().querySelector<HTMLInputElement>(`[formcontrolname="${nombre}"]`)!;
    c.value = valor;
    c.dispatchEvent(new Event('input'));
  }

  it('muestra el club como texto, con enlaces seguros y solo videos de YouTube válidos', async () => {
    await cargar(SITIO);
    expect(el().querySelector('h1')?.textContent).toBe('Club Dragones');
    expect(el().textContent).toContain('<b>Formar</b>'); // nunca se interpreta como HTML
    expect(el().textContent).toContain('6:00 pm – 8:00 pm');
    expect(el().querySelector<HTMLAnchorElement>('a[href^="https://wa.me/573001234567"]')).not.toBeNull();
    expect(el().querySelector<HTMLAnchorElement>('a[href="https://www.instagram.com/dragones/"]')).not.toBeNull();
    const videos = [...el().querySelectorAll<HTMLAnchorElement>('a.video')].map((a) => a.href);
    expect(videos).toEqual(['https://www.youtube.com/watch?v=dQw4w9WgXcQ']);
    expect(el().querySelector<HTMLImageElement>('.foto img')!.getAttribute('src')).toBe(`${API}/publico/fotos/f1?tam=mini`);
    expect(el().textContent).toContain('3 cupos libres');
  });

  it('inscribe un club: exige la autorización de datos y envía el formulario limpio', async () => {
    await cargar(SITIO);
    boton('Inscribir mi club')!.click();
    await estable();
    escribir('nombre_club', 'Halcones VC');
    escribir('ciudad', 'Pereira');
    escribir('delegado_nombre', 'Carlos Gómez');
    escribir('delegado_telefono', '300 123 4567');
    await estable();
    boton('Inscribir club')!.click();
    await estable();
    expect(el().querySelector('dialog [role="alert"]')?.textContent).toContain('autorizar');

    el().querySelector<HTMLInputElement>('[formcontrolname="acepta_datos"]')!.click();
    await estable();
    boton('Inscribir club')!.click();
    const r = backend.expectOne(`${API}/publico/torneos/t1/inscripcion`);
    expect(r.request.body).toEqual({
      nombre_club: 'Halcones VC', ciudad: 'Pereira', delegado_nombre: 'Carlos Gómez', delegado_telefono: '3001234567',
      delegado_email: null, acepta_datos: true, sitio_web: null,
    });
    r.flush({ estado: 'pendiente_pago', mensaje: 'Recibimos la inscripción.' });
    await estable();
    expect(el().querySelector('dialog [role="status"]')?.textContent).toContain('Recibimos la inscripción');
  });

  it('si el sitio no está publicado lo dice y ofrece ingresar', async () => {
    await cargar({ detail: 'no' }, 404);
    expect(el().textContent).toContain('Muy pronto');
    expect(el().querySelector('a[href="/login"]')).not.toBeNull();
  });
});
