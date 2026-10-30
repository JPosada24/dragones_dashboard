import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { registerLocaleData } from '@angular/common';
import localeEsCo from '@angular/common/locales/es-CO';
import { LOCALE_ID } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { PesosPipe } from '../../compartido/pesos.pipe';
import { AuthService } from '../../core/auth/auth.service';
import { API, Usuario } from '../../core/modelos';
import { ResumenPage } from './resumen';
import { ResumenStaff } from './resumen.modelos';

registerLocaleData(localeEsCo);

const conPermisos = (permisos: string[]): Usuario => ({
  id: 'u', email: 'x@club.com', nombre: 'X', rol: 'ADMIN', activo: true, rama: null, permisos,
});

const RESUMEN: ResumenStaff = {
  indicadores: {
    alumnos_activos: 42, alumnos_sin_inscripcion: 3, inscripciones_pendientes: 5, inscripciones_vencen_pronto: 2,
    multas_pendientes: 3, multas_saldo: 6000, alertas: 1,
  },
  alertas: [{ tipo: 'expulsion', titulo: 'Kevin · marcado para expulsión', detalle: 'Mora', cuando: '', ruta: '/inscripciones' }],
  hoy: [{ id: 's', lugar: 'Coliseo', horario: '18:00–20:00', cerrada: false, esperados: 10, presentes: 6,
          justificados: 1, ausentes: 1, sin_marcar: 2 }],
  rifas: [],
  cartera: [{ concepto: 'Multas sin pagar', nota: '3 multas', monto: 6000 }],
  proximo_torneo: null,
};

describe('ResumenPage', () => {
  let backend: HttpTestingController;

  function crear(permisos: string[]) {
    TestBed.configureTestingModule({
      imports: [ResumenPage],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting(), { provide: LOCALE_ID, useValue: 'es-CO' }],
    });
    TestBed.inject(AuthService).usuario.set(conPermisos(permisos));
    backend = TestBed.inject(HttpTestingController);
    const fixture = TestBed.createComponent(ResumenPage);
    fixture.detectChanges();
    return fixture;
  }

  afterEach(() => backend.verify());

  it('el staff ve indicadores, alertas y el entrenamiento de hoy', async () => {
    const fixture = crear(['alumnos.ver_todos']);
    backend.expectOne(`${API}/resumen`).flush(RESUMEN);
    await fixture.whenStable();
    const texto = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(texto).toContain('42');
    expect(texto).toContain('3 registrados sin inscribir');
    expect(texto).toContain('$6.000');
    expect(texto).toContain('Kevin · marcado para expulsión');
    expect(texto).toContain('7/10'); // presentes + justificados sobre esperados
  });

  it('sin alertas no muestra la insignia (solo el mensaje vacío)', async () => {
    const fixture = crear(['alumnos.ver_todos']);
    backend.expectOne(`${API}/resumen`).flush({ ...RESUMEN, alertas: [] });
    await fixture.whenStable();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.insignia')).toBeNull();
    expect(el.textContent).toContain('No hay nada pendiente');
  });

  it('una familia no pide el tablero del staff: ve a sus hijos', async () => {
    const fixture = crear(['alumnos.ver_propios']);
    backend.expectNone(`${API}/resumen`);
    backend.expectOne(`${API}/alumnos`).flush([{ id: 'a1', nombres: 'Laura', apellidos: 'Pérez', rama: 'femenina', es_menor: true }]);
    backend.expectOne((r) => r.url.startsWith(`${API}/sesiones`)).flush([]);
    backend.expectOne(`${API}/alumnos/a1/estado-cuenta`).flush({
      alumno_id: 'a1', inscripcion_estado: 'activo', inscripcion_saldo: 0, multas_pendientes: 1, multas_saldo: 2000,
      rifas: [], total: 2000, al_dia: false, en_mora: false, entra_en_mora: '2027-02-02',
    });
    await fixture.whenStable();
    const texto = (fixture.nativeElement as HTMLElement).textContent ?? '';
    expect(texto).toContain('Laura Pérez');
    expect(texto).toContain('Con saldo');
    expect(texto).toContain('$2.000');
  });

  it('muestra un error claro si la API falla', async () => {
    const fixture = crear(['alumnos.ver_todos']);
    backend.expectOne(`${API}/resumen`).flush(null, { status: 500, statusText: 'Error' });
    await fixture.whenStable();
    expect((fixture.nativeElement as HTMLElement).querySelector('[role="alert"]')).not.toBeNull();
  });
});

describe('PesosPipe', () => {
  it('formatea como en Colombia', () => {
    const p = new PesosPipe();
    expect(p.transform(90000)).toBe('$90.000');
    expect(p.transform(0)).toBe('$0');
    expect(p.transform(null)).toBe('');
  });
});
