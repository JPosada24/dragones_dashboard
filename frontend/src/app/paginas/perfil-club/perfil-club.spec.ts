import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { API } from '../../core/modelos';
import { PerfilClubPage } from './perfil-club';

const PANEL = {
  perfil: {
    nombre: 'Club Dragones', lema: null, ciudad: null, sede: null, mision: 'Formar deportistas', vision: null,
    historia: null, whatsapp: null, correo: null, instagram: null, facebook: null, publicado: false,
  },
  albumes: [{ id: 'a1', nombre: 'Copa', fecha: null, publicado: false, fotos: [{ id: 'f1', ancho: 10, alto: 10 }] }],
  videos: [],
  equipo: [],
};

describe('PerfilClubPage', () => {
  let backend: HttpTestingController;
  let fixture: ComponentFixture<PerfilClubPage>;

  beforeEach(async () => {
    globalThis.URL.createObjectURL ??= () => 'blob:prueba';
    globalThis.URL.revokeObjectURL ??= () => undefined;
    TestBed.configureTestingModule({
      imports: [PerfilClubPage], providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    backend = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(PerfilClubPage);
    fixture.detectChanges();
    backend.expectOne(`${API}/club`).flush(PANEL);
    backend.expectOne(`${API}/club/fotos/f1?tam=mini`).flush(new Blob(['x']));
    await estable();
  });

  afterEach(() => backend.verify());

  const el = () => fixture.nativeElement as HTMLElement;
  const dialogo = () => el().querySelector('dialog')!;
  const boton = (t: string, dentro: ParentNode = el()) =>
    [...dentro.querySelectorAll('button')].find((b) => b.textContent?.trim().startsWith(t));
  async function estable() {
    await fixture.whenStable();
    fixture.detectChanges();
  }

  it('muestra textos, álbumes en borrador y publica el sitio', async () => {
    expect(el().textContent).toContain('Formar deportistas');
    expect(el().textContent).toContain('El sitio está oculto');
    expect(el().textContent).toContain('borrador');
    el().querySelector<HTMLButtonElement>('.estado-sitio [role="switch"]')!.click();
    const r = backend.expectOne(`${API}/club/perfil`);
    expect(r.request.body).toEqual({ publicado: true });
    r.flush({ ...PANEL.perfil, publicado: true });
    await estable();
    expect(el().textContent).toContain('El sitio está publicado');
  });

  it('no sube fotos sin la autorización de los acudientes', async () => {
    boton('add_photo_alternate')!.click();
    await estable();
    const input = dialogo().querySelector<HTMLInputElement>('input[type="file"]')!;
    Object.defineProperty(input, 'files', { value: [new File(['x'], 'a.jpg', { type: 'image/jpeg' })] });
    input.dispatchEvent(new Event('change'));
    boton('Subir', dialogo())!.click();
    await estable();
    expect(dialogo().querySelector('[role="alert"]')?.textContent).toContain('autorización');

    dialogo().querySelector<HTMLInputElement>('[formcontrolname="autorizacion"]')!.click();
    boton('Subir', dialogo())!.click();
    const r = backend.expectOne(`${API}/club/albumes/a1/fotos`);
    expect((r.request.body as FormData).get('autorizacion')).toBe('true');
    r.flush({ id: 'f2', ancho: 10, alto: 10 });
    backend.expectOne(`${API}/club/fotos/f2?tam=mini`).flush(new Blob(['y']));
    await estable();
    expect(el().textContent).toContain('1 foto subida');
  });

  it('agrega un video con el enlace de YouTube', async () => {
    boton('Agregar video')!.click();
    await estable();
    for (const [campo, valor] of [['titulo', 'Resumen'], ['enlace', 'https://youtu.be/dQw4w9WgXcQ']]) {
      const c = dialogo().querySelector<HTMLInputElement>(`[formcontrolname="${campo}"]`)!;
      c.value = valor!;
      c.dispatchEvent(new Event('input'));
    }
    boton('Agregar', dialogo())!.click();
    const r = backend.expectOne(`${API}/club/videos`);
    expect(r.request.body).toEqual({ titulo: 'Resumen', enlace: 'https://youtu.be/dQw4w9WgXcQ' });
    r.flush({ id: 'v1', titulo: 'Resumen', youtube_id: 'dQw4w9WgXcQ', publicado: true });
    await estable();
    expect(el().querySelector('img.video-mini')?.getAttribute('src')).toBe('https://i.ytimg.com/vi/dQw4w9WgXcQ/mqdefault.jpg');
  });
});
