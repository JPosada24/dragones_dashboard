import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { API } from '../../core/modelos';
import { PerfilClubPage } from './perfil-club';

const PANEL = {
  sitio_url: 'https://club.example',
  perfil: {
    nombre: 'Club Dragones', lema: null, ciudad: null, sede: null, fundado_en: null, formacion_intro: null, formacion: null, mision: 'Formar deportistas', vision: null,
    historia: null, whatsapp: null, correo: null, instagram: null, facebook: null, publicado: false,
  },
  albumes: [{ id: 'a1', nombre: 'Copa', fecha: null, publicado: false, fotos: [{ id: 'f1', ancho: 10, alto: 10 }] }],
  videos: [],
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
    expect(el().textContent).toContain('Contenido oculto en el sitio');
    expect(el().querySelector<HTMLAnchorElement>('a[href="https://club.example"]')?.target).toBe('_blank');
    el().querySelector<HTMLButtonElement>('.estado-sitio [role="switch"]')!.click();
    const r = backend.expectOne(`${API}/club/perfil`);
    expect(r.request.body).toEqual({ publicado: true });
    r.flush({ ...PANEL.perfil, publicado: true });
    await estable();
    expect(el().textContent).toContain('Contenido publicado en el sitio');
  });

  it('edita las 6 etapas de la formación y valida cada zona', async () => {
    expect(el().querySelectorAll('.mini-cancha .zona').length).toBe(6);
    expect([...el().querySelectorAll('.zona-num')].map((z) => z.textContent)).toEqual(['4', '3', '2', '5', '6', '1']);
    expect(el().textContent).toContain('etapas de ejemplo');
    el().querySelector<HTMLButtonElement>('[aria-labelledby="titulo-formacion"] .enlace')!.click();
    await estable();
    const titulos = dialogo().querySelectorAll<HTMLInputElement>('[formcontrolname="titulo"]');
    expect(titulos.length).toBe(6);
    expect(titulos[0]!.value).toBe('Primer contacto');
    titulos[2]!.value = 'x';
    titulos[2]!.dispatchEvent(new Event('input'));
    boton('Guardar', dialogo())!.click();
    await estable();
    expect(dialogo().querySelector('[role="alert"]')?.textContent).toContain('Zona 3');
    titulos[2]!.value = 'Juego en la red y bloqueo';
    titulos[2]!.dispatchEvent(new Event('input'));
    boton('Guardar', dialogo())!.click();
    const r = backend.expectOne(`${API}/club/perfil`);
    expect(r.request.body.formacion).toHaveLength(6);
    expect(r.request.body.formacion[2].titulo).toBe('Juego en la red y bloqueo');
    r.flush({ ...PANEL.perfil, formacion: r.request.body.formacion, formacion_intro: r.request.body.formacion_intro });
    await estable();
    expect(el().textContent).toContain('Juego en la red y bloqueo');
    expect(el().textContent).not.toContain('etapas de ejemplo');
  });
});
