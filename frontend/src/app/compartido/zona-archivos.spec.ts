import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ZonaArchivos } from './zona-archivos';

describe('ZonaArchivos', () => {
  let fixture: ComponentFixture<ZonaArchivos>;
  let recibidos: File[][];

  async function crear(multiple: boolean) {
    TestBed.configureTestingModule({ imports: [ZonaArchivos] });
    fixture = TestBed.createComponent(ZonaArchivos);
    fixture.componentRef.setInput('multiple', multiple);
    recibidos = [];
    fixture.componentInstance.elegidos.subscribe((f) => recibidos.push(f));
    fixture.detectChanges();
    await fixture.whenStable();
  }

  const el = () => fixture.nativeElement as HTMLElement;
  const foto = (nombre: string, tipo = 'image/jpeg') => new File(['x'], nombre, { type: tipo });

  function soltar(archivos: File[]) {
    const evento = new Event('drop', { bubbles: true, cancelable: true }) as Event & { dataTransfer: unknown };
    evento.dataTransfer = { files: archivos };
    el().querySelector('label')!.dispatchEvent(evento);
    fixture.detectChanges();
    return evento;
  }

  it('acepta fotos arrastradas y descarta lo que no es imagen', async () => {
    await crear(true);
    const evento = soltar([foto('a.jpg'), foto('b.png', 'image/png'), foto('virus.exe', 'application/x-msdownload')]);
    expect(evento.defaultPrevented).toBe(true); // el navegador no abre el archivo
    expect(recibidos[0]!.map((f) => f.name)).toEqual(['a.jpg', 'b.png']);
    expect(el().textContent).toContain('2 archivos elegidos');
    expect(el().querySelector('[role="alert"]')?.textContent).toContain('1 archivo no es');
  });

  it('en modo de una sola foto se queda con la primera', async () => {
    await crear(false);
    soltar([foto('a.jpg'), foto('b.jpg')]);
    expect(recibidos[0]!.map((f) => f.name)).toEqual(['a.jpg']);
    expect(el().textContent).toContain('a.jpg');
  });

  it('también funciona tocando para elegir', async () => {
    await crear(true);
    const input = el().querySelector<HTMLInputElement>('input[type="file"]')!;
    Object.defineProperty(input, 'files', { value: [foto('c.webp', 'image/webp')] });
    input.dispatchEvent(new Event('change'));
    expect(recibidos[0]!.map((f) => f.name)).toEqual(['c.webp']);
  });
});
