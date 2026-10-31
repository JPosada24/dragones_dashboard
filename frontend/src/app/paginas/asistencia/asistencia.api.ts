import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { Esquema } from '../../core/api/tipos';
import { API } from '../../core/modelos';
import {
  AlertaInasistencia, FilaPlanilla, Horario, HorarioActualizado, Justificacion, Sesion,
} from './asistencia.modelos';

const url = (id: string) => `${API}/sesiones/${encodeURIComponent(id)}`;

/** Acceso a la API de entrenamientos, planillas y justificaciones. La pantalla no arma URLs ni parámetros. */
@Injectable({ providedIn: 'root' })
export class AsistenciaApi {
  private readonly http = inject(HttpClient);

  // ---------- Sesiones y horario ----------
  sesiones(desde: string, hasta: string): Observable<Sesion[]> {
    return this.http.get<Sesion[]>(`${API}/sesiones`, { params: { desde, hasta } });
  }

  crearExtra(datos: Esquema<'SesionCrear'>): Observable<Sesion> {
    return this.http.post<Sesion>(`${API}/sesiones`, datos);
  }

  cancelar(id: string, motivo: string | null): Observable<Sesion> {
    return this.http.post<Sesion>(`${url(id)}/cancelar`, { motivo } satisfies Esquema<'CancelarIn'>);
  }

  reactivar(id: string): Observable<Sesion> {
    return this.http.post<Sesion>(`${url(id)}/reactivar`, {});
  }

  /** Solo sesiones extra (las automáticas salen del horario). */
  eliminar(id: string): Observable<unknown> {
    return this.http.delete(url(id));
  }

  horario(): Observable<Horario> {
    return this.http.get<Horario>(`${API}/sesiones/horario`);
  }

  cambiarHorario(datos: Esquema<'HorarioIn'>): Observable<HorarioActualizado> {
    return this.http.put<HorarioActualizado>(`${API}/sesiones/horario`, datos);
  }

  alertas(): Observable<AlertaInasistencia[]> {
    return this.http.get<AlertaInasistencia[]>(`${API}/sesiones/alertas`);
  }

  // ---------- Planilla ----------
  planilla(sesionId: string): Observable<FilaPlanilla[]> {
    return this.http.get<FilaPlanilla[]>(`${url(sesionId)}/asistencia`);
  }

  marcarGrupo(sesionId: string, datos: Esquema<'MarcarGrupoIn'>): Observable<FilaPlanilla[]> {
    return this.http.post<FilaPlanilla[]>(`${url(sesionId)}/asistencia`, datos);
  }

  marcarPropia(sesionId: string, alumnoId: string): Observable<unknown> {
    return this.http.post(`${url(sesionId)}/asistencia/propia`, { alumno_id: alumnoId } satisfies Esquema<'MarcarPropiaIn'>);
  }

  corregir(sesionId: string, alumnoId: string, datos: Esquema<'CorreccionIn'>): Observable<FilaPlanilla[]> {
    return this.http.patch<FilaPlanilla[]>(`${url(sesionId)}/asistencia/${encodeURIComponent(alumnoId)}`, datos);
  }

  // ---------- Justificaciones ----------
  /** El staff que revisa pide las pendientes; la familia, el historial de las suyas. */
  justificaciones(filtro: { estado?: Justificacion['estado']; limit?: number }): Observable<Justificacion[]> {
    let params = new HttpParams();
    if (filtro.estado) params = params.set('estado', filtro.estado);
    if (filtro.limit) params = params.set('limit', filtro.limit);
    return this.http.get<Justificacion[]>(`${API}/justificaciones`, { params });
  }

  justificar(sesionId: string, datos: Esquema<'JustificarIn'>): Observable<Justificacion> {
    return this.http.post<Justificacion>(`${url(sesionId)}/justificaciones`, datos);
  }

  revisar(justificacionId: string, datos: Esquema<'RevisarIn'>): Observable<Justificacion> {
    return this.http.post<Justificacion>(`${API}/justificaciones/${encodeURIComponent(justificacionId)}/revisar`, datos);
  }
}
