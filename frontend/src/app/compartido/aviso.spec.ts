import { ComponentFixture, TestBed } from '@angular/core/testing';
import { vi } from 'vitest';

import { Aviso } from './aviso';

describe('Aviso', () => {
  let fixture: ComponentFixture<Aviso>;
  let cerrado: number;

  function crear(texto: string, error = false) {
    fixture = TestBed.createComponent(Aviso);
    fixture.componentRef.setInput('texto', texto);
    fixture.componentRef.setInput('error', error);
    cerrado = 0;
    fixture.componentInstance.cerrar.subscribe(() => cerrado++);
    fixture.detectChanges();
  }

  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('se cierra con la X', () => {
    crear('Sesión cancelada');
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('[role="status"]')?.textContent).toContain('Sesión cancelada');
    el.querySelector<HTMLButtonElement>('button[aria-label="Cerrar mensaje"]')!.click();
    expect(cerrado).toBe(1);
  });

  it('el de éxito se cierra solo; el error se queda hasta cerrarlo', () => {
    crear('Guardado');
    vi.advanceTimersByTime(6000);
    expect(cerrado).toBe(1);

    crear('Falló', true);
    expect((fixture.nativeElement as HTMLElement).querySelector('[role="alert"]')).not.toBeNull();
    vi.advanceTimersByTime(60000);
    expect(cerrado).toBe(0);
  });
});
