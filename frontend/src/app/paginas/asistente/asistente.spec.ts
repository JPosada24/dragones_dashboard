import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AuthService } from '../../core/auth/auth.service';
import { API, Usuario } from '../../core/modelos';
import { AsistentePage } from './asistente';

describe('AsistentePage', () => {
  let backend: HttpTestingController;
  let fixture: ComponentFixture<AsistentePage>;

  async function cargar(estado: object, permisos = ['agente.usar', 'alumnos.ver_todos']) {
    TestBed.configureTestingModule({ imports: [AsistentePage], providers: [provideHttpClient(), provideHttpClientTesting()] });
    const usuario: Usuario = { id: 'u', email: 'x@club.com', nombre: 'X', rol: 'ADMIN', activo: true, permisos };
    TestBed.inject(AuthService).usuario.set(usuario);
    backend = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(AsistentePage);
    fixture.detectChanges();
    backend.expectOne(`${API}/agente/estado`).flush(estado);
    await estable();
  }

  afterEach(() => backend.verify());

  const el = () => fixture.nativeElement as HTMLElement;
  const campo = () => el().querySelector<HTMLTextAreaElement>('textarea')!;
  async function estable() {
    await fixture.whenStable();
    fixture.detectChanges();
  }
  async function escribir(texto: string) {
    campo().value = texto;
    campo().dispatchEvent(new Event('input'));
    await estable();
  }

  it('pregunta, muestra la respuesta como texto y reenvía el historial', async () => {
    await cargar({ configurado: true, limite_diario: 40, usados_hoy: 3 });
    expect(el().textContent).toContain('37 preguntas disponibles hoy');
    await escribir('¿Quién debe multas?');
    campo().dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    await estable();
    const r1 = backend.expectOne(`${API}/agente/preguntar`);
    expect(r1.request.body).toEqual({ pregunta: '¿Quién debe multas?', historial: [] });
    expect(el().textContent).toContain('Consultando');
    r1.flush({ texto: '<b>Laura</b> debe $4.000', herramientas: ['multas', 'multas'], restantes_hoy: 36 });
    await estable();
    const burbujas = [...el().querySelectorAll('.burbuja')].map((b) => b.textContent);
    expect(burbujas).toEqual(['¿Quién debe multas?', '<b>Laura</b> debe $4.000']); // nunca HTML
    expect(el().querySelector('.consulto')?.textContent).toContain('Consultó: multas');
    expect(el().textContent).toContain('36 preguntas');

    await escribir('¿Y en mora?');
    el().querySelector<HTMLButtonElement>('[aria-label="Enviar pregunta"]')!.click();
    const r2 = backend.expectOne(`${API}/agente/preguntar`);
    expect(r2.request.body.historial).toEqual([
      { rol: 'user', texto: '¿Quién debe multas?' }, { rol: 'assistant', texto: '<b>Laura</b> debe $4.000' },
    ]);
    r2.flush({ texto: 'Nadie.', herramientas: [], restantes_hoy: 35 });
    await estable();
  });

  it('si falla, la pregunta vuelve al cuadro para reintentar', async () => {
    await cargar({ configurado: true, limite_diario: 40, usados_hoy: 0 });
    el().querySelector<HTMLButtonElement>('.sugerencia')!.click();
    backend.expectOne(`${API}/agente/preguntar`).flush({ detail: 'Llegaste al límite' }, { status: 429, statusText: 'Too Many' });
    await estable();
    expect(el().querySelectorAll('.burbuja').length).toBe(0);
    expect(campo().value).toContain('multas pendientes');
    expect(el().textContent).toContain('Llegaste al límite');
  });

  it('sin configurar no deja escribir; la familia ve sus sugerencias', async () => {
    await cargar({ configurado: false, limite_diario: 40, usados_hoy: 0 }, ['agente.usar', 'alumnos.ver_propios']);
    expect(el().textContent).toContain('No está configurado');
    expect(campo().disabled).toBe(true);
    expect(el().querySelector('.sugerencia')).toBeNull();
  });
});
