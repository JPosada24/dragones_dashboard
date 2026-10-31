import { HttpErrorResponse } from '@angular/common/http';
import { Subject, of, throwError } from 'rxjs';

import { Operacion } from './operacion';

const error422 = new HttpErrorResponse({ status: 422, error: { detail: 'El abono supera el saldo.' } });

describe('Operacion', () => {
  it('marca ocupado mientras la petición está en curso', () => {
    const op = new Operacion();
    const peticion = new Subject<number>();
    let resultado = 0;
    op.ejecutar(peticion, (r) => (resultado = r));
    expect(op.ocupado()).toBe(true);
    peticion.next(7);
    expect(op.ocupado()).toBe(false);
    expect(resultado).toBe(7);
  });

  it('por defecto el error va dentro del popup y no toca el aviso general', () => {
    const op = new Operacion();
    op.exito('Anterior');
    op.ejecutar(throwError(() => error422), () => undefined);
    expect(op.errorDialogo()).toBe('El abono supera el saldo.');
    expect(op.mensaje()).toEqual({ error: false, texto: 'Anterior' });
  });

  it('una acción directa limpia el aviso anterior y muestra su error ahí', () => {
    const op = new Operacion();
    op.exito('Anterior');
    op.ejecutar(throwError(() => error422), () => undefined, { enDialogo: false });
    expect(op.mensaje()).toEqual({ error: true, texto: 'El abono supera el saldo.' });
    expect(op.errorDialogo()).toBeNull();
  });

  it('abrir un popup limpia los mensajes viejos', () => {
    const op = new Operacion();
    op.ejecutar(throwError(() => error422), () => undefined);
    op.exito('Listo');
    let abierto = false;
    op.abrir(() => (abierto = true));
    expect(abierto).toBe(true);
    expect(op.errorDialogo()).toBeNull();
    expect(op.mensaje()).toBeNull();
  });

  it('un nuevo intento borra el error del intento anterior', () => {
    const op = new Operacion();
    op.ejecutar(throwError(() => error422), () => undefined);
    op.ejecutar(of(1), () => undefined);
    expect(op.errorDialogo()).toBeNull();
  });
});
