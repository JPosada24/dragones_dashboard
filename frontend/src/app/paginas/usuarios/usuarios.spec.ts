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
const ALUMNA = {
  id: 'a1', codigo: 'F001', nombres: 'Laura', apellidos: 'Pérez', edad: 12, es_menor: true,
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
});

describe('generarContrasena', () => {
  it('cumple la política y no se repite', () => {
    const a = generarContrasena();
    expect(a).toMatch(/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{16}$/);
    expect(generarContrasena()).not.toBe(a);
  });
});
