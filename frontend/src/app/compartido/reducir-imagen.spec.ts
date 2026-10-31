import { afterEach, describe, expect, it, vi } from 'vitest';

import { reducirImagen } from './reducir-imagen';

const pesada = () => new File([new Uint8Array(3 * 1024 * 1024)], 'DSC0001.JPG', { type: 'image/jpeg' });

describe('reducirImagen', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('una foto liviana se sube tal cual', async () => {
    const f = new File(['x'], 'a.png', { type: 'image/png' });
    expect(await reducirImagen(f)).toBe(f);
  });

  it('si el navegador no puede leerla devuelve el original (decide el servidor)', async () => {
    vi.stubGlobal('createImageBitmap', () => Promise.reject(new Error('formato no soportado')));
    const f = pesada();
    expect(await reducirImagen(f)).toBe(f);
  });

  it('una foto pesada se reduce a JPEG con el lado mayor limitado', async () => {
    const cerrar = vi.fn();
    vi.stubGlobal('createImageBitmap', () => Promise.resolve({ width: 6000, height: 4000, close: cerrar }));
    const lienzo = {
      width: 0, height: 0,
      getContext: () => ({ drawImage: vi.fn() }),
      toBlob: (ok: (b: Blob) => void, tipo: string) => ok(new Blob(['liviana'], { type: tipo })),
    };
    vi.spyOn(document, 'createElement').mockReturnValueOnce(lienzo as unknown as HTMLCanvasElement);
    const r = await reducirImagen(pesada());
    expect([lienzo.width, lienzo.height]).toEqual([2560, 1707]);
    expect(r.name).toBe('DSC0001.jpg');
    expect(r.type).toBe('image/jpeg');
    expect(r.size).toBeLessThan(1024);
    expect(cerrar).toHaveBeenCalled();
  });
});
