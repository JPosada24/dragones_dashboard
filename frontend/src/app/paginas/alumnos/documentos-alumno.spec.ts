import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { API } from '../../core/modelos';
import { Documento } from './alumnos.modelos';
import { DocumentosAlumno } from './documentos-alumno';

const DOC: Documento = {
  id: 'd1', tipo: 'eps', nombre_original: 'eps.pdf', mime: 'application/pdf', tamano: 2048, creado_en: '2026-10-01T10:00:00-05:00',
};

describe('DocumentosAlumno', () => {
  let backend: HttpTestingController;
  let fixture: ComponentFixture<DocumentosAlumno>;

  async function crear(puedeEditar: boolean) {
    TestBed.configureTestingModule({ imports: [DocumentosAlumno], providers: [provideHttpClient(), provideHttpClientTesting()] });
    backend = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(DocumentosAlumno);
    fixture.componentRef.setInput('alumnoId', 'a1');
    fixture.componentRef.setInput('documentos', [DOC]);
    fixture.componentRef.setInput('puedeEditar', puedeEditar);
    await estable();
  }

  afterEach(() => backend.verify());

  const el = () => fixture.nativeElement as HTMLElement;
  const dialogo = () => el().querySelector('dialog')!;
  const boton = (t: string, dentro: ParentNode = el()) =>
    [...dentro.querySelectorAll('button')].find((b) => b.textContent?.trim().endsWith(t));
  async function estable() {
    await fixture.whenStable();
    fixture.detectChanges();
  }

  it('la familia solo ve y descarga: sin subir ni eliminar', async () => {
    await crear(false);
    expect(el().textContent).toContain('Certificado de EPS');
    expect(boton('Subir')).toBeUndefined();
    expect(el().querySelector('[aria-label="Eliminar eps.pdf"]')).toBeNull();
  });

  it('sube un documento (arrastrable) y aparece primero en la lista', async () => {
    await crear(true);
    boton('Subir')!.click();
    await estable();
    const select = dialogo().querySelector<HTMLSelectElement>('[formcontrolname="tipo"]')!;
    select.value = 'identidad';
    select.dispatchEvent(new Event('change'));
    const input = dialogo().querySelector<HTMLInputElement>('input[type="file"]')!;
    Object.defineProperty(input, 'files', { value: [new File(['%PDF'], 'ti.pdf', { type: 'application/pdf' })] });
    input.dispatchEvent(new Event('change'));
    await estable();
    boton('Subir', dialogo())!.click();
    const r = backend.expectOne(`${API}/alumnos/a1/documentos`);
    expect((r.request.body as FormData).get('tipo')).toBe('identidad');
    r.flush({ ...DOC, id: 'd2', tipo: 'identidad', nombre_original: 'ti.pdf' });
    await estable();
    expect(el().querySelector('dialog')).toBeNull();
    expect(el().querySelector('.documento-tipo')?.textContent).toBe('Documento de identidad');
    expect(el().textContent).toContain('Documento subido.');
  });

  it('elimina tras confirmar', async () => {
    await crear(true);
    el().querySelector<HTMLButtonElement>('[aria-label="Eliminar eps.pdf"]')!.click();
    await estable();
    boton('Eliminar', dialogo())!.click();
    backend.expectOne((r) => r.method === 'DELETE' && r.url === `${API}/alumnos/a1/documentos/d1`).flush(null);
    await estable();
    expect(el().textContent).toContain('Sin documentos.');
  });
});
