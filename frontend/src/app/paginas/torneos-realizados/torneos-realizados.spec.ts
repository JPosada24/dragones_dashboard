import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { API } from '../../core/modelos';
import { TorneosRealizadosPage } from './torneos-realizados';

const COPA = {
  id: 't1', nombre: 'Copa Dragones 2025', fecha: '2025-08-16', lugar: 'Coliseo Mayor', resumen: 'Campeón: Halcones.',
  album_id: 'a1', publicado: true, anuncio: 'abcd1234', anuncio_ancho: 1080, anuncio_alto: 1350,
};
const ALBUM = { id: 'a1', nombre: 'Fotos Copa 2025', fecha: null, publicado: true, fotos: [], portada: null };
const URL = `${API}/club/torneos-realizados`;

describe('TorneosRealizadosPage', () => {
  let backend: HttpTestingController;
  let fixture: ComponentFixture<TorneosRealizadosPage>;

  beforeEach(async () => {
    globalThis.URL.createObjectURL ??= () => 'blob:prueba';
    globalThis.URL.revokeObjectURL ??= () => undefined;
    TestBed.configureTestingModule({
      imports: [TorneosRealizadosPage], providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    backend = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(TorneosRealizadosPage);
    fixture.detectChanges();
    backend.expectOne(URL).flush([COPA]);
    backend.expectOne(`${API}/club/albumes`).flush([ALBUM]);
    backend.expectOne(`${URL}/t1/anuncio`).flush(new Blob(['x'])); // anuncio con el token
    await estable();
  });

  afterEach(() => backend.verify());

  const el = () => fixture.nativeElement as HTMLElement;
  const dialogo = () => el().querySelector('dialog')!;
  const boton = (t: string, dentro: ParentNode = el()) =>
    [...dentro.querySelectorAll('button')].find((b) => b.textContent?.trim().includes(t));
  async function estable() {
    await fixture.whenStable();
    fixture.detectChanges();
  }
  function escribir(campo: string, valor: string) {
    const c = dialogo().querySelector<HTMLInputElement>(`[formcontrolname="${campo}"]`)!;
    c.value = valor;
    c.dispatchEvent(new Event('input'));
  }

  it('muestra cada torneo con su anuncio entero, reseña y álbum enlazado', () => {
    const tarjeta = el().querySelector('.tarjeta')!;
    expect(tarjeta.querySelector('h2')?.textContent).toBe('Copa Dragones 2025');
    const img = tarjeta.querySelector<HTMLImageElement>('.anuncio img')!;
    expect(img.getAttribute('width')).toBe('1080');
    expect(img.alt).toBe('Anuncio de Copa Dragones 2025');
    expect(tarjeta.textContent).toContain('Coliseo Mayor');
    expect(tarjeta.querySelector('.album')?.textContent).toContain('Fotos Copa 2025');
  });

  it('agrega un torneo con su anuncio y lo ubica por fecha', async () => {
    boton('Agregar torneo')!.click();
    await estable();
    escribir('nombre', 'Copa Dragones 2026');
    escribir('fecha', '2026-03-14');
    const input = dialogo().querySelector<HTMLInputElement>('input[type="file"]')!;
    Object.defineProperty(input, 'files', { value: [new File(['x'], 'afiche.jpg', { type: 'image/jpeg' })] });
    input.dispatchEvent(new Event('change'));
    boton('Guardar', dialogo())!.click();
    const crear = backend.expectOne(URL);
    expect(crear.request.method).toBe('POST');
    expect(crear.request.body).toEqual({
      nombre: 'Copa Dragones 2026', fecha: '2026-03-14', lugar: null, resumen: null, album_id: null, publicado: true,
    });
    const nuevo = { ...COPA, id: 't2', nombre: 'Copa Dragones 2026', fecha: '2026-03-14', lugar: null, resumen: null,
      album_id: null, anuncio: null, anuncio_ancho: null, anuncio_alto: null };
    crear.flush(nuevo);
    const anuncio = backend.expectOne(`${URL}/t2/anuncio`);
    expect(anuncio.request.method).toBe('POST');
    anuncio.flush({ ...nuevo, anuncio: 'ffff0000', anuncio_ancho: 1080, anuncio_alto: 1350 });
    backend.expectOne(`${URL}/t2/anuncio`).flush(new Blob(['y']));
    await estable();
    expect([...el().querySelectorAll('.tarjeta h2')].map((h) => h.textContent)).toEqual([
      'Copa Dragones 2026', 'Copa Dragones 2025']);
    expect(el().textContent).toContain('Copa Dragones 2026 agregado a los torneos realizados');
  });

  it('pide nombre y fecha antes de enviar', async () => {
    boton('Agregar torneo')!.click();
    await estable();
    escribir('nombre', 'Copa sin fecha');
    boton('Guardar', dialogo())!.click();
    await estable();
    expect(dialogo().textContent).toContain('Escribe el nombre del torneo y la fecha');
  });

  it('quita el anuncio y el álbum al editar', async () => {
    el().querySelector<HTMLButtonElement>('[aria-label="Editar Copa Dragones 2025"]')!.click();
    await estable();
    boton('Quitar anuncio', dialogo())!.click();
    const select = dialogo().querySelector<HTMLSelectElement>('[formcontrolname="album_id"]')!;
    select.value = '';
    select.dispatchEvent(new Event('change'));
    boton('Guardar', dialogo())!.click();
    const r = backend.expectOne(`${URL}/t1`);
    expect(r.request.method).toBe('PATCH');
    expect(r.request.body.album_id).toBeNull();
    r.flush({ ...COPA, album_id: null });
    const quitar = backend.expectOne(`${URL}/t1/anuncio`);
    expect(quitar.request.method).toBe('DELETE');
    quitar.flush({ ...COPA, album_id: null, anuncio: null, anuncio_ancho: null, anuncio_alto: null });
    await estable();
    expect(el().querySelector('.sin-anuncio')).not.toBeNull();
    expect(el().querySelector('.album')).toBeNull();
  });

  it('oculta con el interruptor y elimina con confirmación', async () => {
    el().querySelector<HTMLButtonElement>('[role="switch"]')!.click();
    const r = backend.expectOne(`${URL}/t1`);
    expect(r.request.body).toEqual({ publicado: false });
    r.flush({ ...COPA, publicado: false });
    await estable();
    expect(el().querySelector('.tarjeta.oculto')).not.toBeNull();

    el().querySelector<HTMLButtonElement>('[aria-label="Eliminar Copa Dragones 2025"]')!.click();
    await estable();
    boton('Eliminar', dialogo())!.click();
    const borrar = backend.expectOne(`${URL}/t1`);
    expect(borrar.request.method).toBe('DELETE');
    borrar.flush(null, { status: 204, statusText: 'No Content' });
    await estable();
    expect(el().querySelectorAll('.tarjeta').length).toBe(0);
    expect(el().textContent).toContain('Copa Dragones 2025 salió de los torneos realizados');
  });
});
