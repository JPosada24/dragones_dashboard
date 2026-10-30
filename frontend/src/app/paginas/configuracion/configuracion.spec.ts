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
  { clave: 'dias_aviso_mora', valor: 15, descripcion: '' },
];

const ROLES = {
  permisos: [
    { codigo: 'asistencia.marcar_grupo', descripcion: 'Marcar la asistencia de la planilla' },
    { codigo: 'config.editar', descripcion: 'Cambiar parámetros críticos' },
    { codigo: 'pagos.registrar', descripcion: 'Registrar pagos' },
  ],
  roles: [
    { codigo: 'SUPERADMIN', nombre: 'SuperAdmin', descripcion: null, permisos: ['asistencia.marcar_grupo', 'config.editar', 'pagos.registrar'] },
    { codigo: 'ADMIN', nombre: 'Admin', descripcion: null, permisos: ['asistencia.marcar_grupo', 'pagos.registrar'] },
    { codigo: 'ENTRENADOR', nombre: 'Entrenador', descripcion: null, permisos: ['asistencia.marcar_grupo'] },
  ],
};

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
    backend.expectOne(`${API}/configuracion/roles`).flush(ROLES);
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

  it('muestra los parámetros con valor y unidad, los recordatorios y la matriz de roles', async () => {
    await cargar(['config.ver', 'config.editar']);
    const caja = el().querySelector('[aria-label^="Cambiar Valor de la inscripción"]')!;
    expect(caja.querySelector('.valor')?.textContent).toBe('$90.000');
    expect(caja.querySelector('.unidad')?.textContent).toBe('COP');
    expect(el().querySelector('[aria-label^="Cambiar Hora de cierre"] .unidad')?.textContent).toBe('11:59 pm');
    const cuando = [...el().querySelectorAll('.cuando')].map((c) => c.textContent?.trim());
    expect(cuando).toEqual(['7 DÍAS', '1 DÍA', 'VENCIDO', '15 DÍAS', 'mail']);
    const filas = [...el().querySelectorAll('.matriz tbody tr')].map((f) => f.textContent?.replace(/\s+/g, ''));
    expect(filas).toContain('Cambiarparámetroscríticos✓——');
    expect(filas).toContain('Cobrarmultasyrifas✓✓—');
  });

  it('cambia un valor: el campo empieza vacío y se valida antes de enviar', async () => {
    await cargar(['config.ver', 'config.editar']);
    el().querySelector<HTMLButtonElement>('[aria-label^="Cambiar Valor de la inscripción"]')!.click();
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
    expect(el().querySelector('[aria-label^="Cambiar Valor de la inscripción"] .valor')?.textContent).toBe('$100.000');
  });

  it('los días de recordatorio se escriben separados por comas', async () => {
    await cargar(['config.ver', 'config.editar']);
    boton('Cambiar días')!.click();
    await estable();
    escribir('1, 15, 7');
    boton('Guardar', dialogo())!.click();
    const r = backend.expectOne(`${API}/configuracion/recordatorios_dias_antes`);
    expect(r.request.body).toEqual({ valor: [15, 7, 1] });
    r.flush({ clave: 'recordatorios_dias_antes', valor: [15, 7, 1], descripcion: '' });
  });

  it('el interruptor activa la expulsión automática', async () => {
    await cargar(['config.ver', 'config.editar']);
    const interruptor = el().querySelector<HTMLButtonElement>('[role="switch"]')!;
    expect(interruptor.getAttribute('aria-checked')).toBe('false');
    interruptor.click();
    const r = backend.expectOne(`${API}/configuracion/expulsion_automatica`);
    expect(r.request.body).toEqual({ valor: true });
    r.flush({ clave: 'expulsion_automatica', valor: true, descripcion: '' });
    await estable();
    expect(interruptor.getAttribute('aria-checked')).toBe('true');
    expect(el().textContent).toContain('Expulsión automática activada');
  });

  it('el Admin solo consulta', async () => {
    await cargar(['config.ver']);
    expect(el().querySelector('[aria-label^="Cambiar"]')).toBeNull();
    expect(el().querySelector<HTMLButtonElement>('[role="switch"]')!.disabled).toBe(true);
    expect(boton('Probar correo')).toBeUndefined();
    expect(boton('Cambiar días')).toBeUndefined();
    expect(el().querySelector('.caja-valor .valor')?.textContent).toBeTruthy();
  });

  it('prueba el correo del club', async () => {
    await cargar(['config.ver', 'config.editar']);
    boton('Probar correo')!.click();
    backend.expectOne(`${API}/notificaciones/correo-prueba`).flush({ enviado: true, modo: 'smtp', detalle: 'Enviado a d***@club.com.' });
    await estable();
    expect(el().textContent).toContain('Correo de prueba enviado');
  });
});
