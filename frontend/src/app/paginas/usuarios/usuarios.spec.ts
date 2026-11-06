import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AuthService } from '../../core/auth/auth.service';
import { API, Usuario } from '../../core/modelos';
import { UsuariosPage, generarContrasena } from './usuarios';

const YO: Usuario = { id: 'yo', email: 'dueno@club.com', nombre: 'Dueño', rol: 'SUPERADMIN', activo: true, permisos: ['usuarios.gestionar'] };
const CUENTAS = [
  { ...YO, vinculado_a: null },
  { id: 'u2', email: 'coach@club.com', nombre: 'Ana Coach', rol: 'ENTRENADOR', activo: true, permisos: [], vinculado_a: null },
  { id: 'u3', email: 'marta@club.com', nombre: 'Marta Gómez', rol: 'MIEMBRO', activo: true, permisos: [], vinculado_a: 'Acudiente de F001 Laura' },
];
const ROLES = {
  permisos: [
    { codigo: 'alumnos.ver_todos', descripcion: 'Ver fichas de todos los alumnos' },
    { codigo: 'config.editar', descripcion: 'Cambiar parámetros críticos' },
    { codigo: 'pagos.registrar', descripcion: 'Registrar pagos' },
    { codigo: 'reportes.ver', descripcion: 'Ver los reportes de ingresos' },
    { codigo: 'usuarios.gestionar', descripcion: 'Crear usuarios' },
  ],
  roles: [
    { codigo: 'SUPERADMIN', nombre: 'SuperAdmin', descripcion: null, permisos: ['alumnos.ver_todos', 'config.editar', 'pagos.registrar', 'reportes.ver', 'usuarios.gestionar'] },
    { codigo: 'ADMIN', nombre: 'Admin', descripcion: null, permisos: ['alumnos.ver_todos', 'config.editar', 'pagos.registrar', 'reportes.ver'] },
    { codigo: 'ENTRENADOR', nombre: 'Entrenador', descripcion: null, permisos: ['alumnos.ver_todos'] },
    { codigo: 'MIEMBRO', nombre: 'Miembro', descripcion: null, permisos: [] },
  ],
  personalizables: ['alumnos.ver_todos', 'config.editar', 'pagos.registrar', 'reportes.ver'],
};
const ALUMNA = {
  id: 'a1', codigo: 'F001', nombres: 'Laura', apellidos: 'Pérez', edad: 12, es_menor: true,
  autorizacion: { nombre: 'Marta Gómez', imagen: true, registrada_en: '2026-01-10T15:00:00Z' },
  acudientes: [{ acudiente_id: 'ac1', nombres: 'Marta', apellidos: 'Gómez', telefono: '3001234567', parentesco: 'madre', principal: true }],
};

describe('UsuariosPage', () => {
  let backend: HttpTestingController;
  let fixture: ComponentFixture<UsuariosPage>;

  beforeEach(async () => {
    TestBed.configureTestingModule({ imports: [UsuariosPage], providers: [provideHttpClient(), provideHttpClientTesting()] });
    TestBed.inject(AuthService).usuario.set(YO);
    backend = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(UsuariosPage);
    fixture.detectChanges();
    backend.expectOne(`${API}/usuarios`).flush(CUENTAS);
    backend.expectOne(`${API}/usuarios/roles`).flush(ROLES);
    await estable();
  });

  afterEach(() => backend.verify());

  const el = () => fixture.nativeElement as HTMLElement;
  const dialogo = () => [...el().querySelectorAll('dialog')].at(-1)!;
  const boton = (t: string, dentro: ParentNode = el()) =>
    [...dentro.querySelectorAll('button')].find((b) => b.textContent?.replace(/\s+/g, ' ').trim().startsWith(t)) as HTMLButtonElement | undefined;
  async function estable() {
    await fixture.whenStable();
    fixture.detectChanges();
  }
  function escribir(selector: string, valor: string) {
    const campo = dialogo().querySelector<HTMLInputElement | HTMLSelectElement>(selector)!;
    campo.value = valor;
    campo.dispatchEvent(new Event(campo instanceof HTMLSelectElement ? 'change' : 'input'));
  }

  it('lista las cuentas con su rol y a quién pertenecen, y filtra por rol', async () => {
    expect(el().querySelectorAll('.cuenta').length).toBe(3);
    expect(el().textContent).toContain('Acudiente de F001 Laura');
    boton('Entrenador')!.click();
    await estable();
    expect(el().querySelectorAll('.cuenta').length).toBe(1);
  });

  it('crea la cuenta de un acudiente buscando a su alumno, y muestra la contraseña una vez', async () => {
    boton('person_add Nueva cuenta')!.click();
    await estable();
    escribir('[formcontrolname="nombre"]', 'Marta Gómez');
    escribir('[formcontrolname="email"]', 'marta2@club.com');
    boton('Generar', dialogo())!.click();
    escribir('[formcontrolname="rol"]', 'MIEMBRO');
    await estable();
    const clave = dialogo().querySelector<HTMLInputElement>('[formcontrolname="password"]')!.value;
    expect(clave).toMatch(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{16}$/);

    escribir('input[type="search"]', 'Laura');
    await new Promise((r) => setTimeout(r, 350));
    backend.expectOne((r) => r.url === `${API}/alumnos`).flush([ALUMNA]);
    await estable();
    dialogo().querySelector<HTMLButtonElement>('.candidato')!.click();
    await estable();
    boton('Crear cuenta', dialogo())!.click();
    const r = backend.expectOne((x) => x.method === 'POST' && x.url === `${API}/usuarios`);
    expect(r.request.body).toEqual({
      nombre: 'Marta Gómez', email: 'marta2@club.com', password: clave, rol: 'MIEMBRO', vincular_acudiente_id: 'ac1',
    });
    r.flush({ ...CUENTAS[2]!, email: 'marta2@club.com' });
    backend.expectOne(`${API}/usuarios`).flush(CUENTAS);
    await estable();
    expect(dialogo().textContent).toContain(clave);
  });

  it('un alumno menor no puede tener cuenta propia; el entrenador no lleva rama', async () => {
    boton('person_add Nueva cuenta')!.click();
    await estable();
    escribir('[formcontrolname="rol"]', 'MIEMBRO');
    await estable();
    (dialogo().querySelector<HTMLInputElement>('input[value="alumno"]')!).click();
    escribir('input[type="search"]', 'Laura');
    await new Promise((r) => setTimeout(r, 350));
    backend.expectOne((r) => r.url === `${API}/alumnos`).flush([ALUMNA]);
    await estable();
    expect(dialogo().querySelector<HTMLButtonElement>('.candidato')!.disabled).toBe(true);

    escribir('[formcontrolname="nombre"]', 'Ana');
    escribir('[formcontrolname="email"]', 'ana@club.com');
    escribir('[formcontrolname="password"]', 'ClaveSegura123');
    escribir('[formcontrolname="rol"]', 'ENTRENADOR');
    await estable();
    expect(dialogo().querySelector('[formcontrolname="rama"]')).toBeNull();
    expect(dialogo().textContent).toContain('Ambas ramas');
    boton('Crear cuenta', dialogo())!.click();
    const r = backend.expectOne((x) => x.method === 'POST' && x.url === `${API}/usuarios`);
    expect(r.request.body).toEqual({ nombre: 'Ana', email: 'ana@club.com', password: 'ClaveSegura123', rol: 'ENTRENADOR' });
    r.flush(CUENTAS[1]!);
    backend.expectOne(`${API}/usuarios`).flush(CUENTAS);
    await estable();
  });

  it('en su propia cuenta no se puede cambiar el rol ni desactivar', async () => {
    el().querySelector<HTMLButtonElement>('[aria-label="Editar la cuenta de Dueño"]')!.click();
    await estable();
    expect(dialogo().querySelector('[formcontrolname="rol"]')).toBeNull();
    expect(dialogo().textContent).toContain('no puedes cambiar tu propio rol');
  });

  it('sin el permiso no aparece la opción de eliminar', () => {
    expect(el().querySelector('[aria-label^="Eliminar la cuenta"]')).toBeNull();
  });

  it('el SuperAdmin elimina otra cuenta (nunca la suya) tras confirmar', async () => {
    TestBed.inject(AuthService).usuario.set({ ...YO, permisos: ['usuarios.gestionar', 'usuarios.eliminar'] });
    await estable();
    expect(el().querySelector('[aria-label="Eliminar la cuenta de Dueño"]')).toBeNull();
    el().querySelector<HTMLButtonElement>('[aria-label="Eliminar la cuenta de Marta Gómez"]')!.click();
    await estable();
    expect(dialogo().textContent).toContain('Acudiente de F001 Laura: sus datos se conservan');
    boton('Eliminar cuenta', dialogo())!.click();
    const r = backend.expectOne(`${API}/usuarios/u3`);
    expect(r.request.method).toBe('DELETE');
    r.flush(null, { status: 204, statusText: 'No Content' });
    await estable();
    expect(el().textContent).not.toContain('marta@club.com');
    expect(el().textContent).toContain('Se eliminó la cuenta de Marta Gómez');
  });

  it('restablece la contraseña de otra cuenta', async () => {
    el().querySelector<HTMLButtonElement>('[aria-label="Cambiar la contraseña de Ana Coach"]')!.click();
    await estable();
    escribir('[formcontrolname="password"]', 'corta');
    boton('Cambiar', dialogo())!.click();
    await estable();
    expect(dialogo().querySelector('[role="alert"]')?.textContent).toContain('12 caracteres');
    escribir('[formcontrolname="password"]', 'NuevaClave2026x');
    boton('Cambiar', dialogo())!.click();
    const r = backend.expectOne(`${API}/usuarios/u2`);
    expect(r.request.body).toEqual({ password: 'NuevaClave2026x' });
    r.flush(CUENTAS[1]!);
    await estable();
    expect(dialogo().textContent).toContain('NuevaClave2026x');
  });
  it('la vista «Roles y permisos» muestra la matriz (antes estaba en Configuración)', async () => {
    [...el().querySelectorAll<HTMLButtonElement>('.vistas button')].find((b) => b.textContent?.includes('Roles y permisos'))!.click();
    await estable();
    const filas = [...el().querySelectorAll('.matriz tbody tr')].map((f) => f.textContent?.replace(/\s+/g, ''));
    expect(filas).toContain('Cambiarparámetroscríticos✓✓——');
    expect(filas).toContain('Cuentasypermisos✓———');
    expect(el().querySelector('.cuentas')).toBeNull();
  });

  it('ajusta los permisos de un entrenador: marca lo distinto a su rol y guarda la lista completa', async () => {
    // Solo Admin y Entrenador se ajustan; nunca la propia cuenta ni una de familia.
    expect(el().querySelector('[aria-label="Permisos de Ana Coach"]')).not.toBeNull();
    expect(el().querySelector('[aria-label="Permisos de Marta Gómez"]')).toBeNull();
    expect(el().querySelector('[aria-label="Permisos de Dueño"]')).toBeNull();

    el().querySelector<HTMLButtonElement>('[aria-label="Permisos de Ana Coach"]')!.click();
    await estable();
    backend.expectOne(`${API}/usuarios/u2/permisos`).flush({
      rol: 'ENTRENADOR', personalizable: true, de_rol: ['alumnos.ver_todos'], concedidos: [], quitados: [],
      efectivos: ['alumnos.ver_todos'],
    });
    await estable();
    expect(dialogo().textContent).not.toContain('Crear usuarios'); // lo de cuentas no se ofrece
    expect(dialogo().textContent).toContain('Igual que su rol.');

    const casilla = (texto: string) => [...dialogo().querySelectorAll<HTMLLabelElement>('label.permiso')]
      .find((l) => l.textContent?.includes(texto))!.querySelector('input')!;
    casilla('Ver los reportes').click();
    casilla('Ver fichas de todos').click();
    await estable();
    expect(dialogo().querySelector('.marca.agregado')?.closest('label')?.textContent).toContain('reportes');
    expect(dialogo().querySelector('.marca.quitado')?.closest('label')?.textContent).toContain('fichas');
    expect(dialogo().textContent).toContain('2 cambios respecto a su rol.');

    boton('Guardar', dialogo())!.click();
    const r = backend.expectOne(`${API}/usuarios/u2/permisos`);
    expect(r.request.method).toBe('PUT');
    expect(r.request.body).toEqual({ permisos: ['reportes.ver'] });
    r.flush({ rol: 'ENTRENADOR', personalizable: true, de_rol: ['alumnos.ver_todos'], concedidos: ['reportes.ver'],
      quitados: ['alumnos.ver_todos'], efectivos: ['reportes.ver'] });
    await estable();
    backend.expectOne(`${API}/usuarios`).flush(CUENTAS.map((c) => (c.id === 'u2' ? { ...c, permisos_personalizados: true } : c)));
    await estable();
    expect(el().textContent).toContain('Permisos de Ana Coach guardados (2 distintos a su rol).');
    expect(el().querySelector('.chip-ajuste')).not.toBeNull();
  });
});

describe('generarContrasena', () => {
  it('cumple la política y no se repite', () => {
    const a = generarContrasena();
    expect(a).toMatch(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{16}$/);
    expect(generarContrasena()).not.toBe(a);
  });
});
