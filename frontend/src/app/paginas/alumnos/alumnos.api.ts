import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, forkJoin } from 'rxjs';

import { Esquema } from '../../core/api/tipos';
import { API } from '../../core/modelos';
import { inscripcionUrl } from '../inscripciones/inscribir';
import { Inscripcion } from '../inscripciones/inscripciones.modelos';
import { Acudiente, Alumno, Documento, EstadoCuenta, Nivel, Rama, RegistroHistorial } from './alumnos.modelos';

const url = (id: string) => `${API}/alumnos/${encodeURIComponent(id)}`;

export interface FiltroAlumnos {
  limite: number;
  buscar?: string;
  rama?: Rama | '';
  nivel?: Nivel | '';
  activo?: boolean;
}

/** Todo lo que la ficha muestra de un alumno, pedido en paralelo. */
export interface FichaAlumno {
  alumno: Alumno;
  cuenta: EstadoCuenta;
  historial: RegistroHistorial[];
  documentos: Documento[];
  inscripciones: Inscripcion[];
}

export type VinculoNuevo = Esquema<'VinculoIn'>;
export type AlumnoNuevo = Esquema<'AlumnoCrear'>;
export type AcudienteNuevo = Esquema<'AcudienteCrear'>;
export type Autorizacion = Esquema<'AutorizacionIn'>;
export type AltaConInscripcion = Esquema<'AlumnoNuevoIn'>;

/** Acceso a la API de alumnos, acudientes y documentos. La pantalla no arma URLs ni parámetros. */
@Injectable({ providedIn: 'root' })
export class AlumnosApi {
  private readonly http = inject(HttpClient);

  listar(f: FiltroAlumnos): Observable<Alumno[]> {
    let params = new HttpParams().set('limit', f.limite);
    if (f.buscar && f.buscar.trim().length >= 2) params = params.set('buscar', f.buscar.trim());
    if (f.rama) params = params.set('rama', f.rama);
    if (f.nivel) params = params.set('nivel', f.nivel);
    if (f.activo !== undefined) params = params.set('activo', f.activo);
    return this.http.get<Alumno[]>(`${API}/alumnos`, { params });
  }

  ficha(id: string, anio: string): Observable<FichaAlumno> {
    return forkJoin({
      alumno: this.http.get<Alumno>(url(id)),
      cuenta: this.http.get<EstadoCuenta>(`${url(id)}/estado-cuenta`),
      historial: this.http.get<RegistroHistorial[]>(`${url(id)}/asistencia`),
      documentos: this.http.get<Documento[]>(`${url(id)}/documentos`),
      inscripciones: this.http.get<Inscripcion[]>(`${API}/inscripciones`, {
        params: new HttpParams().set('alumno_id', id).set('anio', anio),
      }),
    });
  }

  crear(datos: AlumnoNuevo): Observable<Alumno> {
    return this.http.post<Alumno>(`${API}/alumnos`, datos);
  }

  /** Ficha + inscripción de hoy + primer pago en una sola transacción. */
  inscribirNuevo(datos: AltaConInscripcion): Observable<Inscripcion> {
    return this.http.post<Inscripcion>(`${API}/inscripciones/alumno-nuevo`, datos);
  }

  actualizar(id: string, cambios: Partial<Esquema<'AlumnoActualizar'>>): Observable<Alumno> {
    return this.http.patch<Alumno>(url(id), cambios);
  }

  eliminar(id: string): Observable<unknown> {
    return this.http.delete(url(id));
  }

  /** Documento completo (solo Admin/SuperAdmin; el servidor deja registro en la auditoría). */
  documentoIdentidad(id: string): Observable<Esquema<'DocumentoIdentidadOut'>> {
    return this.http.get<Esquema<'DocumentoIdentidadOut'>>(`${url(id)}/documento-identidad`);
  }

  registrarAutorizacion(id: string, datos: Autorizacion): Observable<Alumno> {
    return this.http.put<Alumno>(`${url(id)}/autorizacion`, datos);
  }

  abonar(inscripcionId: string, datos: Esquema<'PagoIn'>): Observable<Inscripcion> {
    return this.http.post<Inscripcion>(`${inscripcionUrl(inscripcionId)}/pagos`, datos);
  }

  // ---------- Acudientes ----------
  /** Por documento completo: así se reutiliza el acudiente de un hermano sin duplicarlo. */
  buscarAcudiente(tipoDocumento: string, documento: string): Observable<Acudiente[]> {
    const params = new HttpParams().set('tipo_documento', tipoDocumento).set('documento', documento);
    return this.http.get<Acudiente[]>(`${API}/acudientes`, { params });
  }

  crearAcudiente(datos: AcudienteNuevo): Observable<Acudiente> {
    return this.http.post<Acudiente>(`${API}/acudientes`, datos);
  }

  vincularAcudiente(alumnoId: string, vinculo: VinculoNuevo): Observable<Alumno> {
    return this.http.post<Alumno>(`${url(alumnoId)}/acudientes`, vinculo);
  }

  desvincularAcudiente(alumnoId: string, acudienteId: string): Observable<Alumno> {
    return this.http.delete<Alumno>(`${url(alumnoId)}/acudientes/${encodeURIComponent(acudienteId)}`);
  }

  // ---------- Documentos ----------
  subirDocumento(alumnoId: string, tipo: string, archivo: File): Observable<Documento> {
    const datos = new FormData();
    datos.append('tipo', tipo);
    datos.append('archivo', archivo);
    return this.http.post<Documento>(`${url(alumnoId)}/documentos`, datos);
  }

  descargarDocumento(alumnoId: string, documentoId: string): Observable<Blob> {
    return this.http.get(`${url(alumnoId)}/documentos/${encodeURIComponent(documentoId)}/archivo`, {
      responseType: 'blob',
    });
  }

  eliminarDocumento(alumnoId: string, documentoId: string): Observable<unknown> {
    return this.http.delete(`${url(alumnoId)}/documentos/${encodeURIComponent(documentoId)}`);
  }
}
