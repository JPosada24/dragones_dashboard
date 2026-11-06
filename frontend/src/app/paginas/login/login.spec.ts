import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { API } from '../../core/modelos';
import { LoginPage } from './login';

const DEMO = {
  clave: 'DemoDragones2026',
  cuentas: [
    { rol: 'SUPERADMIN', email: 'superadmin@example.com', nombre: 'Julián Demo (dueño)' },
    { rol: 'ENTRENADOR', email: 'entrenador@example.com', nombre: 'Carlos Demo (entrenador asistente)' },
  ],
};

describe('LoginPage', () => {
  let backend: HttpTestingController;
  let fixture: ComponentFixture<LoginPage>;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [LoginPage], providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    backend = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(LoginPage);
    fixture.detectChanges();
  });

  afterEach(() => backend.verify());

  const el = () => fixture.nativeElement as HTMLElement;
  async function estable() {
    await fixture.whenStable();
    fixture.detectChanges();
  }

  it('fuera del demo no muestra cuentas de prueba', async () => {
    backend.expectOne(`${API}/demo`).flush({ detail: 'No encontrado' }, { status: 404, statusText: 'Not Found' });
    await estable();
    expect(el().querySelector('.demo')).toBeNull();
  });

  it('en el demo entra con una cuenta de prueba con un clic', async () => {
    backend.expectOne(`${API}/demo`).flush(DEMO);
    await estable();
    expect(el().querySelector('.demo')?.textContent).toContain('DemoDragones2026');
    const botones = [...el().querySelectorAll<HTMLButtonElement>('.cuenta')];
    expect(botones.map((b) => b.querySelector('b')?.textContent)).toEqual(['SuperAdmin', 'Entrenador']);
    botones[1]!.click();
    const r = backend.expectOne(`${API}/auth/login`);
    expect(r.request.body).toEqual({ email: 'entrenador@example.com', password: 'DemoDragones2026' });
    r.flush({ detail: 'x' }, { status: 401, statusText: 'Unauthorized' });
    await estable();
    expect(el().textContent).toContain('Correo o contraseña incorrectos.');
  });
});
