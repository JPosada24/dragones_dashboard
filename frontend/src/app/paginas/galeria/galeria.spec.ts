import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { API } from '../../core/modelos';
import { GaleriaPage } from './galeria';

const FOTOS = [1, 2, 3].map((n) => ({ id: `f${n}`, ancho: 10, alto: 10 }));
const ALBUMES = [
  { id: 'a1', nombre: 'Copa Caldas', fecha: null, publicado: true, fotos: FOTOS },
  { id: 'a2', nombre: 'Entrenamientos', fecha: null, publicado: false, fotos: [] },
];
const C = `${API}/club`;

describe('GaleriaPage', () => {
  let backend: HttpTestingController;
  let fixture: ComponentFixture<GaleriaPage>;

  async function cargar(album?: string) {
    globalThis.URL.createObjectURL ??= () => 'blob:prueba';
    globalThis.URL.revokeObjectURL ??= () => undefined;
    TestBed.configureTestingModule({
      imports: [GaleriaPage], providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    backend = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(GaleriaPage);
    if (album) fixture.componentRef.setInput('album', album);
    fixture.detectChanges();
    backend.expectOne(`${C}/albumes`).flush(structuredClone(ALBUMES));
    backend.expectOne(`${C}/videos`).flush([]);
    await estable();
  }

  afterEach(() => backend.verify());

  const el = () => fixture.nativeElement as HTMLElement;
  const dialogo = () => el().querySelector('dialog')!;
  const boton = (t: string, dentro: ParentNode = el()) =>
    [...dentro.querySelectorAll('button')].find((b) => b.textContent?.trim().includes(t));
  async function estable() {
    await fixture.whenStable();
    fixture.detectChanges();
  }

  it('la lista muestra los álbumes como carpetas y solo pide la portada de cada uno', async () => {
    await cargar();
    backend.expectOne(`${C}/fotos/f1?tam=mini`).flush(new Blob(['x'])); // portada; f2 y f3 no se piden aquí
    await estable();
    const albumes = [...el().querySelectorAll<HTMLAnchorElement>('a.album')];
    expect(albumes.map((a) => a.querySelector('.nombre')?.textContent)).toEqual(['Copa Caldas', 'Entrenamientos']);
    expect(albumes[0]!.getAttribute('href')).toContain('album=a1');
    expect(albumes[1]!.textContent).toContain('Borrador');
    expect(el().querySelector('.foto')).toBeNull(); // las fotos no se ven sueltas
  });

  it('dentro del álbum se marcan varias fotos y se eliminan juntas', async () => {
    await cargar('a1');
    for (const f of FOTOS) backend.expectOne(`${C}/fotos/${f.id}?tam=mini`).flush(new Blob(['x']));
    await estable();
    expect(el().querySelector('#titulo-album')?.textContent).toBe('Copa Caldas');
    const fotos = el().querySelectorAll<HTMLButtonElement>('button.foto');
    expect(fotos.length).toBe(3);
    fotos[0]!.click();
    fotos[2]!.click();
    await estable();
    expect(fotos[0]!.getAttribute('aria-pressed')).toBe('true');
    expect(el().textContent).toContain('2 seleccionadas');

    boton('Eliminar 2')!.click();
    await estable();
    boton('Eliminar 2', dialogo())!.click();
    const r = backend.expectOne(`${C}/fotos/eliminar`);
    expect(r.request.body).toEqual({ ids: ['f1', 'f3'] });
    r.flush({ eliminadas: 2 });
    await estable();
    expect(el().querySelectorAll('button.foto').length).toBe(1);
    expect(el().textContent).toContain('2 fotos eliminadas');
  });

  it('«Seleccionar todas» marca y desmarca todas las fotos', async () => {
    await cargar('a1');
    for (const f of FOTOS) backend.expectOne(`${C}/fotos/${f.id}?tam=mini`).flush(new Blob(['x']));
    await estable();
    boton('Seleccionar todas')!.click();
    await estable();
    expect(el().textContent).toContain('3 seleccionadas');
    boton('Quitar selección')!.click();
    await estable();
    expect(el().querySelectorAll('button.foto[aria-pressed="true"]').length).toBe(0);
  });

  it('un álbum vacío invita a subir fotos', async () => {
    await cargar('a2');
    expect(el().textContent).toContain('Este álbum aún no tiene fotos');
    expect(boton('Seleccionar todas')).toBeUndefined();
  });
});
