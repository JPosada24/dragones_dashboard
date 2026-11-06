import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { AuthService } from '../../core/auth/auth.service';
import { API, Usuario } from '../../core/modelos';
import { TutorialService } from '../../core/tutorial.service';
import { Tutorial } from './tutorial';

const ADMIN = ['alumnos.ver_todos', 'eventos.gestionar', 'club.editar'];
const ENTRENADOR = ['alumnos.ver_todos', 'asistencia.marcar_grupo'];

const usuario = (permisos: string[], extra: Partial<Usuario> = {}): Usuario => ({
  id: 'u', email: 'ana@club.com', nombre: 'Ana Ruiz', rol: 'ADMIN', activo: true, tutorial_visto: false, permisos, ...extra,
});

describe('Tutorial', () => {
  let backend: HttpTestingController;
  let fixture: ComponentFixture<Tutorial>;
  let servicio: TutorialService;
  let auth: AuthService;

  function preparar(u: Usuario) {
    TestBed.configureTestingModule({
      imports: [Tutorial], providers: [provideHttpClient(), provideHttpClientTesting(), provideRouter([])],
    });
    auth = TestBed.inject(AuthService);
    auth.usuario.set(u);
    servicio = TestBed.inject(TutorialService);
    backend = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(Tutorial);
    fixture.detectChanges();
  }

  afterEach(() => backend.verify());

  const el = () => fixture.nativeElement as HTMLElement;
  const boton = (t: string) => [...el().querySelectorAll('button')].find((b) => b.textContent?.trim() === t);
  async function estable() {
    await fixture.whenStable();
    fixture.detectChanges();
  }

  it('solo enseña las secciones que la persona tiene en su menú', () => {
    preparar(usuario(ENTRENADOR, { rol: 'ENTRENADOR' }));
    const titulos = servicio.pasos().map((p) => p.titulo);
    expect(titulos[0]).toBe('¡Hola, Ana!');
    expect(titulos).toContain('Alumnos');
    expect(titulos).toContain('Asistencia');
    expect(titulos).not.toContain('Torneos');
    expect(titulos).not.toContain('Perfil del club');
    expect(titulos.at(-1)).toBe('¡A jugar!');
  });

  it('sale solo al staff que nunca lo vio', () => {
    preparar(usuario(ADMIN));
    expect(servicio.debeMostrarse()).toBe(true);
    auth.usuario.set(usuario(ADMIN, { tutorial_visto: true }));
    expect(servicio.debeMostrarse()).toBe(false);
    auth.usuario.set(usuario([], { rol: 'MIEMBRO' }));
    expect(servicio.debeMostrarse()).toBe(false);
  });

  it('recorre los pasos con Brasa y al terminar queda visto en el servidor', async () => {
    preparar(usuario(ADMIN));
    servicio.iniciar();
    await estable();
    expect(el().querySelector('dialog h2')?.textContent).toBe('¡Hola, Ana!');
    expect(el().querySelector('app-dragon')?.getAttribute('data-pose')).toBe('saluda');
    expect(boton('Atrás')).toBeUndefined();

    boton('Siguiente')!.click();
    await estable();
    expect(el().querySelector('dialog h2')?.textContent).toBe('Resumen');
    expect(el().querySelector('app-dragon')?.getAttribute('data-pose')).toBe('senala');
    boton('Atrás')!.click();
    await estable();
    expect(el().querySelector('dialog h2')?.textContent).toBe('¡Hola, Ana!');

    while (boton('Siguiente')) {
      boton('Siguiente')!.click();
      await estable();
    }
    expect(el().querySelector('app-dragon')?.getAttribute('data-pose')).toBe('remata');
    expect(boton('Saltar')).toBeUndefined(); // en el último paso ya no hay qué saltar
    boton('¡Listo!')!.click();
    const r = backend.expectOne(`${API}/auth/tutorial`);
    expect(r.request.method).toBe('POST');
    r.flush(null, { status: 204, statusText: 'No Content' });
    await estable();
    expect(el().querySelector('dialog')).toBeNull();
    expect(auth.usuario()?.tutorial_visto).toBe(true);
  });

  it('«Saltar» también lo deja visto, y verlo otra vez no vuelve a avisar al servidor', async () => {
    preparar(usuario(ADMIN));
    servicio.iniciar();
    await estable();
    boton('Saltar')!.click();
    backend.expectOne(`${API}/auth/tutorial`).flush(null, { status: 204, statusText: 'No Content' });
    await estable();
    expect(el().querySelector('dialog')).toBeNull();

    servicio.iniciar(); // desde la ayuda
    await estable();
    boton('Saltar')!.click();
    backend.expectNone(`${API}/auth/tutorial`);
  });

  it('resalta el elemento del paso si está a la vista', async () => {
    preparar(usuario(ADMIN));
    const enlace = document.createElement('a');
    enlace.dataset['tutorial'] = 'seccion:';
    enlace.getBoundingClientRect = () => ({ top: 100, left: 10, right: 210, bottom: 140, width: 200, height: 40 }) as DOMRect;
    document.body.appendChild(enlace);
    servicio.iniciar();
    await estable();
    expect(el().querySelector('.foco')).toBeNull(); // la bienvenida va al centro
    boton('Siguiente')!.click();
    await estable();
    const foco = el().querySelector<HTMLElement>('.foco')!;
    expect(foco.style.top).toBe('94px');
    expect(foco.style.width).toBe('212px');
    enlace.remove();
  });
});
