import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { API } from '../../core/modelos';
import { HabeasPage, Solicitud } from './habeas';

const solicitud = (id: string, extra: Partial<Solicitud> = {}): Solicitud => ({
  id, tipo: 'consulta', titular: 'Marta Gómez', contacto: 'marta@correo.com', descripcion: 'Qué datos tienen de Laura.',
  recibida_el: '2026-11-02', vence_el: '2026-11-17', dias_habiles_restantes: 8, prorrogada: false, motivo_prorroga: null,
  estado: 'en_tramite', respuesta: null, respondida_en: null, ...extra,
});

describe('HabeasPage', () => {
  let backend: HttpTestingController;
  let fixture: ComponentFixture<HabeasPage>;

  beforeEach(async () => {
    TestBed.configureTestingModule({ imports: [HabeasPage], providers: [provideHttpClient(), provideHttpClientTesting()] });
    backend = TestBed.inject(HttpTestingController);
    fixture = TestBed.createComponent(HabeasPage);
    fixture.detectChanges();
    backend.expectOne(`${API}/habeas`).flush([
      solicitud('s1'), solicitud('s2', { dias_habiles_restantes: -1, titular: 'Pedro Ruiz' }),
      solicitud('s3', { estado: 'respondida', respuesta: 'Enviado por correo.', respondida_en: '2026-11-05T10:00:00Z' }),
    ]);
    await estable();
  });

  afterEach(() => backend.verify());

  const el = () => fixture.nativeElement as HTMLElement;
  const dialogo = () => el().querySelector('dialog')!;
  const boton = (t: string, dentro: ParentNode = el()) =>
    [...dentro.querySelectorAll('button')].find((b) => b.textContent?.includes(t));
  async function estable() {
    await fixture.whenStable();
    fixture.detectChanges();
  }

  it('muestra las en trámite con su plazo y marca la vencida', async () => {
    expect(el().querySelectorAll('.solicitud').length).toBe(2);
    const plazos = [...el().querySelectorAll('.plazo')].map((p) => [p.textContent?.trim(), p.getAttribute('data-tono')]);
    expect(plazos).toEqual([['8 días hábiles', 'ok'], ['Vencida', 'mal']]);
    // A una vencida ya no se le amplía el plazo.
    const vencida = el().querySelectorAll('.solicitud')[1]!;
    expect(boton('Ampliar plazo', vencida)).toBeUndefined();
    boton('Respondidas')!.click();
    await estable();
    expect(el().textContent).toContain('Enviado por correo.');
  });

  it('registra una solicitud nueva (el tipo no trae valor por defecto)', async () => {
    boton('Registrar solicitud')!.click();
    await estable();
    boton('Registrar', dialogo().querySelector('.acciones')!)!.click();
    await estable();
    expect(dialogo().querySelector('[role="alert"]')?.textContent).toContain('Completa el tipo');
    const campo = (n: string, v: string) => {
      const c = dialogo().querySelector<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>(`[formcontrolname="${n}"]`)!;
      c.value = v;
      c.dispatchEvent(new Event(c instanceof HTMLSelectElement ? 'change' : 'input'));
    };
    campo('tipo', 'reclamo');
    campo('titular', 'Ana Ruiz');
    campo('contacto', '3001234567');
    campo('descripcion', 'Corrijan mi número de teléfono, por favor.');
    boton('Registrar', dialogo().querySelector('.acciones')!)!.click();
    const r = backend.expectOne((x) => x.method === 'POST' && x.url === `${API}/habeas`);
    expect(r.request.body).toMatchObject({ tipo: 'reclamo', titular: 'Ana Ruiz', recibida_el: null });
    r.flush(solicitud('s4', { tipo: 'reclamo', titular: 'Ana Ruiz' }));
    await estable();
    expect(el().querySelectorAll('.solicitud').length).toBe(3);
    expect(el().textContent).toContain('Solicitud registrada.');
  });
});
