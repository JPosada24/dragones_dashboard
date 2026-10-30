import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AuthService } from '../../core/auth/auth.service';
import { API, Usuario } from '../../core/modelos';
import { ConfiguracionPage } from './configuracion';

const PARAMETROS = [
  { clave: 'valor_inscripcion', valor: 90000, descripcion: '' },
  { clave: 'plazo_pago_dias', valor: 30, descripcion: '' },
  { clave: 'recordatorios_dias_antes', valor: [7, 1], descripcion: '' },
  { clave: 'hora_cierre_asistencia', valor: '23:59', descripcion: '' },
  { clave: 'expulsion_automatica', valor: false, descripcion: '' },
];

describe('ConfiguracionPage', () => {
  let backend: HttpTestingController;
  let fixture: ComponentFixture<ConfiguracionPage>;

  async function cargar(permisos: string[]) {
    TestBed.configureTestingModule({ imports: [ConfiguracionPage], providers: [provideHttpClient(), provideHttpClientTesting()] });
    const usuario: Usuario = { id: 'u', email: 'x@club.com', nombre: 'X', rol: 'SUPERADMIN', activo: true, permisos };
    TestBed.inject(AuthService).usuario.set(usuario);
    backend = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(ConfiguracionPage);
    fixture.detectChanges();
    backend.expectOne(`${API}/configuracion`).flush(PARAMETROS);
    await estable();
  }

  afterEach(() => backend.verify());

  const el = () => fixture.nativeElement as HTMLElement;
  const dialogo = () => el().querySelector('dialog')!;
  const boton = (t: string, dentro: ParentNode = el()) =>
    [...dentro.querySelectorAll('button')].find((b) => b.textContent?.trim().startsWith(t)) as HTMLButtonElement | undefined;
  async function estable() {
    await fixture.whenStable();
    fixture.detectChanges();
  }
  function escribir(valor: string) {
    const c = dialogo().querySelector<HTMLInputElement>('[formcontrolname="valor"]')!;
    c.value = valor;
    c.dispatchEvent(new Event('input'));
  }

  it('muestra los parámetros agrupados y en formato legible', async () => {
    await cargar(['config.ver', 'config.editar']);
    const texto = el().textContent ?? '';
    expect(texto).toContain('$90.000');
    expect(texto).toContain('30 días');
    expect(texto).toContain('7 y 1 días antes');
    expect(texto).toContain('Apagada');
  });

  it('cambia un valor: el campo empieza vacío y se valida antes de enviar', async () => {
    await cargar(['config.ver', 'config.editar']);
    el().querySelector<HTMLButtonElement>('[aria-label="Cambiar Valor de la inscripción"]')!.click();
    await estable();
    const campo = dialogo().querySelector<HTMLInputElement>('[formcontrolname="valor"]')!;
    expect(campo.value).toBe('');
    expect(campo.placeholder).toBe('Actual: 90000');
    escribir('noventa');
    boton('Guardar', dialogo())!.click();
    await estable();
    expect(dialogo().querySelector('[role="alert"]')?.textContent).toContain('número entero');
    escribir('100.000');
    boton('Guardar', dialogo())!.click();
    const r = backend.expectOne(`${API}/configuracion/valor_inscripcion`);
    expect(r.request.body).toEqual({ valor: 100000 });
    r.flush({ clave: 'valor_inscripcion', valor: 100000, descripcion: '' });
    await estable();
    expect(el().textContent).toContain('$100.000');
  });

  it('las listas se escriben separadas por comas', async () => {
    await cargar(['config.ver', 'config.editar']);
    el().querySelector<HTMLButtonElement>('[aria-label="Cambiar Recordatorios de pago"]')!.click();
    await estable();
    escribir('1, 15, 7');
    boton('Guardar', dialogo())!.click();
    const r = backend.expectOne(`${API}/configuracion/recordatorios_dias_antes`);
    expect(r.request.body).toEqual({ valor: [15, 7, 1] });
    r.flush({ clave: 'recordatorios_dias_antes', valor: [15, 7, 1], descripcion: '' });
  });

  it('el Admin solo consulta', async () => {
    await cargar(['config.ver']);
    expect(el().querySelector('[aria-label^="Cambiar"]')).toBeNull();
    expect(boton('mail Probar correo')).toBeUndefined();
  });

  it('prueba el correo del club', async () => {
    await cargar(['config.ver', 'config.editar']);
    boton('mail Probar correo')!.click();
    backend.expectOne(`${API}/notificaciones/correo-prueba`).flush({ enviado: true, modo: 'smtp', detalle: 'Enviado a d***@club.com.' });
    await estable();
    expect(el().textContent).toContain('Correo de prueba enviado');
  });
});
