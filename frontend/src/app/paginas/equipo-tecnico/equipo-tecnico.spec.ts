import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { API } from '../../core/modelos';
import { EquipoTecnicoPage } from './equipo-tecnico';

const ANA = { id: 'i1', nombre: 'Ana Ruiz', cargo: 'Entrenadora', bio: null, orden: 0, publicado: true, foto: 'abcd1234' };
const URL = `${API}/club/equipo`;

describe('EquipoTecnicoPage', () => {
  let backend: HttpTestingController;
  let fixture: ComponentFixture<EquipoTecnicoPage>;

  beforeEach(async () => {
    globalThis.URL.createObjectURL ??= () => 'blob:prueba';
    globalThis.URL.revokeObjectURL ??= () => undefined;
    TestBed.configureTestingModule({
      imports: [EquipoTecnicoPage], providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    backend = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(EquipoTecnicoPage);
    fixture.detectChanges();
    backend.expectOne(URL).flush([ANA]);
    backend.expectOne(`${URL}/i1/foto`).flush(new Blob(['x'])); // foto con el token
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

  it('muestra cada entrenador con su foto y las pestañas del perfil del club', async () => {
    expect(el().querySelector('.tarjeta h2')?.textContent).toBe('Ana Ruiz');
    expect(el().querySelector('.tarjeta .foto img')).not.toBeNull();
    const pestanas = [...el().querySelectorAll('app-pestanas a')].map((a) => a.textContent?.trim());
    expect(pestanas).toEqual(['web Contenido del sitio', 'sports Equipo técnico']);
  });

  it('agrega un entrenador y sube su foto', async () => {
    boton('Agregar entrenador')!.click();
    await estable();
    escribir('nombre', 'Carlos Vélez');
    escribir('cargo', 'Entrenador · Avanzado');
    const input = dialogo().querySelector<HTMLInputElement>('input[type="file"]')!;
    Object.defineProperty(input, 'files', { value: [new File(['x'], 'carlos.jpg', { type: 'image/jpeg' })] });
    input.dispatchEvent(new Event('change'));
    boton('Guardar', dialogo())!.click();
    const crear = backend.expectOne(URL);
    expect(crear.request.method).toBe('POST');
    expect(crear.request.body).toEqual({ nombre: 'Carlos Vélez', cargo: 'Entrenador · Avanzado', bio: null, orden: 0, publicado: true });
    const nuevo = { ...ANA, id: 'i2', nombre: 'Carlos Vélez', cargo: 'Entrenador · Avanzado', foto: null };
    crear.flush(nuevo);
    const foto = backend.expectOne(`${URL}/i2/foto`);
    expect(foto.request.method).toBe('POST');
    foto.flush({ ...nuevo, foto: 'ffff0000' });
    backend.expectOne(`${URL}/i2/foto`).flush(new Blob(['y']));
    await estable();
    expect(el().querySelectorAll('.tarjeta').length).toBe(2);
    expect(el().textContent).toContain('Carlos Vélez agregado al equipo técnico');
  });

  it('oculta con el interruptor y quita con confirmación', async () => {
    el().querySelector<HTMLButtonElement>('[role="switch"]')!.click();
    const r = backend.expectOne(`${URL}/i1`);
    expect(r.request.body).toEqual({ publicado: false });
    r.flush({ ...ANA, publicado: false });
    await estable();
    expect(el().querySelector('.tarjeta.oculto')).not.toBeNull();

    el().querySelector<HTMLButtonElement>('[aria-label="Quitar a Ana Ruiz"]')!.click();
    await estable();
    boton('Quitar', dialogo())!.click();
    const borrar = backend.expectOne(`${URL}/i1`);
    expect(borrar.request.method).toBe('DELETE');
    borrar.flush(null, { status: 204, statusText: 'No Content' });
    await estable();
    expect(el().querySelectorAll('.tarjeta').length).toBe(0);
  });
});
