import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { Esquema } from '../../core/api/tipos';
import { API } from '../../core/modelos';

export type Ingresos = Esquema<'IngresosOut'>;
export type IngresoMes = Esquema<'IngresoMesOut'>;

@Injectable({ providedIn: 'root' })
export class ReportesApi {
  private readonly http = inject(HttpClient);

  ingresos(anio: number): Observable<Ingresos> {
    return this.http.get<Ingresos>(`${API}/reportes/ingresos`, { params: { anio } });
  }

  /** CSV de movimientos (con el token: no es un enlace público). */
  movimientos(desde: string, hasta: string): Observable<Blob> {
    return this.http.get(`${API}/reportes/movimientos.csv`, { params: { desde, hasta }, responseType: 'blob' });
  }
}
