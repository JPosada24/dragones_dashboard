import { Pipe, PipeTransform } from '@angular/core';

const FORMATO = new Intl.NumberFormat('es-CO', { maximumFractionDigits: 0 });

/** 90000 → "$90.000" (igual que los mensajes del backend). */
@Pipe({ name: 'pesos' })
export class PesosPipe implements PipeTransform {
  transform(valor: number | null | undefined): string {
    return valor == null ? '' : `$${FORMATO.format(valor)}`;
  }
}
