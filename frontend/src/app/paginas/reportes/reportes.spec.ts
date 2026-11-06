import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AuthService } from '../../core/auth/auth.service';
import { API, Usuario } from '../../core/modelos';
import { Ingresos } from './reportes.api';
import { ReportesPage } from './reportes';

const ANIO = new Date().getFullYear();
const vacio = (mes: number) => ({ mes, inscripciones: 0, multas: 0, rifas: 0, torneos: 0, total: 0 });
const DATOS: Ingresos = {
  anio: ANIO,
  total: 230000,
  meses: Array.from({ length: 12 }, (_, i) => vacio(i + 1)).map((m) =>
    m.mes === 2 ? { ...m, inscripciones: 180000, total: 180000 }
      : m.mes === 3 ? { ...m, multas: 4000, rifas: 40000, torneos: 6000, total: 50000 } : m),
};
const usuario = (permisos: string[]): Usuario =>
  ({ id: 'u1', email: 'a@club.com', nombre: 'Ana', rol: 'ADMIN', activo: true, tutorial_visto: true, permisos });

describe('ReportesPage', () => {
  let backend: HttpTestingController;
  let fixture: ComponentFixture<ReportesPage>;

  async function crear(permisos: string[]) {
    TestBed.configureTestingModule({ imports: [ReportesPage], providers: [provideHttpClient(), provideHttpClientTesting()] });
    TestBed.inject(AuthService).usuario.set(usuario(permisos));
    backend = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(ReportesPage);
    fixture.detectChanges();
    backend.expectOne((r) => r.url === `${API}/reportes/ingresos` && r.params.get('anio') === String(ANIO)).flush(DATOS);
    await estable();
  }

  afterEach(() => backend.verify());

  const el = () => fixture.nativeElement as HTMLElement;
  async function estable() {
    await fixture.whenStable();
    fixture.detectChanges();
  }

  it('muestra los indicadores y una fila por mes con su barra proporcional', async () => {
    await crear(['reportes.ver']);
    expect(el().querySelector('.kpi-valor')?.textContent).toContain('230.000');
    expect(el().textContent).toContain('Febrero'); // mejor mes
    const filas = el().querySelectorAll('tbody tr');
    expect(filas.length).toBe(12);
    expect((filas[1]!.querySelector('.barra-mes') as HTMLElement).style.width).toBe('100%');
    expect((filas[2]!.querySelector('.barra-mes') as HTMLElement).style.width).toBe('28%');
    expect(el().querySelector('.exportar')).toBeNull(); // sin reportes.exportar no aparece la descarga
  });

  it('cambia de año', async () => {
    await crear(['reportes.ver']);
    (el().querySelector('[aria-label="Año anterior"]') as HTMLButtonElement).click();
    backend.expectOne((r) => r.params.get('anio') === String(ANIO - 1)).flush({ ...DATOS, anio: ANIO - 1 });
    await estable();
    expect(el().querySelector('.anio-texto')?.textContent).toBe(String(ANIO - 1));
  });

  it('el SuperAdmin descarga los movimientos de un rango válido', async () => {
    globalThis.URL.createObjectURL ??= () => 'blob:prueba';
    globalThis.URL.revokeObjectURL ??= () => undefined;
    await crear(['reportes.ver', 'reportes.exportar']);
    const [desde, hasta] = el().querySelectorAll<HTMLInputElement>('.exportar input[type="date"]');
    desde!.value = '2026-03-31';
    desde!.dispatchEvent(new Event('input'));
    hasta!.value = '2026-03-01';
    hasta!.dispatchEvent(new Event('input'));
    (el().querySelector('.exportar button[type="submit"]') as HTMLButtonElement).click();
    await estable();
    expect(el().textContent).toContain('Elige un rango válido'); // al revés no se pide nada
    hasta!.value = '2026-04-30';
    hasta!.dispatchEvent(new Event('input'));
    (el().querySelector('.exportar button[type="submit"]') as HTMLButtonElement).click();
    const r = backend.expectOne((x) => x.url === `${API}/reportes/movimientos.csv`);
    expect(r.request.params.get('desde')).toBe('2026-03-31');
    r.flush(new Blob(['fecha;concepto']));
    await estable();
    expect(el().textContent).toContain('Movimientos descargados.');
  });
});
