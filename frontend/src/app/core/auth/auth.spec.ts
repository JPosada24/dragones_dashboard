import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { Router, provideRouter } from '@angular/router';

import { API, TokenOut, Usuario } from '../modelos';
import { seccionesVisibles } from '../secciones';
import { authInterceptor } from './auth.interceptor';
import { AuthService, rutaSegura } from './auth.service';

const usuario = (permisos: string[] = []): Usuario => ({
  id: 'u1', email: 'root@club.com', nombre: 'Julian Posada', rol: 'SUPERADMIN', activo: true, rama: null, permisos,
});
const token = (t: string, permisos: string[] = []): TokenOut => ({
  access_token: t, token_type: 'bearer', expires_in: 900, usuario: usuario(permisos),
});

describe('Sesión (AuthService + interceptor)', () => {
  let http: HttpClient;
  let backend: HttpTestingController;
  let auth: AuthService;
  let router: Router;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(withInterceptors([authInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    http = TestBed.inject(HttpClient);
    backend = TestBed.inject(HttpTestingController);
    auth = TestBed.inject(AuthService);
    router = TestBed.inject(Router);
    vi.spyOn(router, 'navigate').mockResolvedValue(true);
  });

  afterEach(() => backend.verify());

  function ingresar(permisos: string[] = []): void {
    auth.login('root@club.com', 'Clave').subscribe();
    backend.expectOne(`${API}/auth/login`).flush(token('t1', permisos));
  }

  it('guarda el token solo en memoria (nunca en el almacenamiento del navegador)', () => {
    ingresar();
    expect(auth.token()).toBe('t1');
    expect(auth.autenticado()).toBe(true);
    expect(JSON.stringify({ ...localStorage })).not.toContain('t1');
    expect(JSON.stringify({ ...sessionStorage })).not.toContain('t1');
  });

  it('agrega el token a la API propia pero nunca a otros dominios', () => {
    ingresar();
    http.get(`${API}/alumnos`).subscribe();
    http.get('https://otro-sitio.com/api/v1/alumnos').subscribe();
    expect(backend.expectOne(`${API}/alumnos`).request.headers.get('Authorization')).toBe('Bearer t1');
    expect(backend.expectOne('https://otro-sitio.com/api/v1/alumnos').request.headers.has('Authorization')).toBe(false);
  });

  it('ante un 401 renueva una sola vez para varias peticiones y las reintenta', () => {
    ingresar();
    const respuestas: unknown[] = [];
    http.get(`${API}/a`).subscribe((r) => respuestas.push(r));
    http.get(`${API}/b`).subscribe((r) => respuestas.push(r));
    backend.expectOne(`${API}/a`).flush(null, { status: 401, statusText: 'No autenticado' });
    backend.expectOne(`${API}/b`).flush(null, { status: 401, statusText: 'No autenticado' });

    backend.expectOne(`${API}/auth/refresh`).flush(token('t2')); // una sola renovación compartida
    const a = backend.expectOne(`${API}/a`);
    const b = backend.expectOne(`${API}/b`);
    expect(a.request.headers.get('Authorization')).toBe('Bearer t2');
    a.flush({ ok: 'a' });
    b.flush({ ok: 'b' });
    expect(respuestas).toHaveLength(2);
  });

  it('si no se puede renovar, cierra la sesión y manda al login', () => {
    ingresar();
    let fallo = false;
    http.get(`${API}/a`).subscribe({ error: () => (fallo = true) });
    backend.expectOne(`${API}/a`).flush(null, { status: 401, statusText: 'No autenticado' });
    backend.expectOne(`${API}/auth/refresh`).flush(null, { status: 401, statusText: 'Sesión expirada' });
    expect(fallo).toBe(true);
    expect(auth.autenticado()).toBe(false);
    expect(router.navigate).toHaveBeenCalledWith(['/login'], { queryParams: { expirada: 1 } });
  });

  it('un 401 del propio login no dispara renovación (evita bucles)', () => {
    auth.login('x@club.com', 'mala').subscribe({ error: () => undefined });
    backend.expectOne(`${API}/auth/login`).flush(null, { status: 401, statusText: 'Credenciales' });
    backend.expectNone(`${API}/auth/refresh`);
  });

  it('logout limpia la sesión aunque falle la red', async () => {
    ingresar();
    const cierre = auth.logout();
    backend.expectOne(`${API}/auth/logout`).error(new ProgressEvent('error'));
    await cierre;
    expect(auth.token()).toBeNull();
    expect(router.navigate).toHaveBeenCalledWith(['/login']);
  });

  it('el menú solo muestra las secciones permitidas', () => {
    ingresar(['alumnos.ver_propios']);
    const rutas = seccionesVisibles((p) => auth.tieneAlguno(p)).map((s) => s.ruta);
    expect(rutas).toContain('alumnos');
    expect(rutas).not.toContain('configuracion');
    expect(rutas).not.toContain('torneos');
    expect(rutas).not.toContain('usuarios');
  });
});

describe('rutaSegura (volver tras el login)', () => {
  it('acepta rutas internas', () => {
    expect(rutaSegura('/alumnos?x=1')).toBe('/alumnos?x=1');
  });

  it('rechaza redirecciones a otros sitios', () => {
    for (const malo of ['https://malo.com', '//malo.com', '/\\malo.com', 'javascript:alert(1)', '', null]) {
      expect(rutaSegura(malo)).toBe('/');
    }
  });
});
