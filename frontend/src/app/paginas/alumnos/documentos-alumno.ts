import { DatePipe } from '@angular/common';
import { ChangeDetectionStrategy, Component, inject, input, linkedSignal, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { Aviso } from '../../compartido/aviso';
import { Dialogo } from '../../compartido/dialogo';
import { Operacion } from '../../compartido/operacion';
import { ZonaArchivos } from '../../compartido/zona-archivos';
import { AlumnosApi } from './alumnos.api';
import { Documento } from './alumnos.modelos';

export const TIPOS_ARCHIVO: { valor: Documento['tipo']; texto: string }[] = [
  { valor: 'identidad', texto: 'Documento de identidad' },
  { valor: 'eps', texto: 'Certificado de EPS' },
  { valor: 'consentimiento', texto: 'Consentimiento informado' },
  { valor: 'certificado_medico', texto: 'Certificado médico' },
  { valor: 'foto', texto: 'Foto' },
  { valor: 'otro', texto: 'Otro' },
];

/** Documentos de un alumno en su ficha: lista, subir (cifrado en el servidor), descargar con el token y eliminar. */
@Component({
  selector: 'app-documentos-alumno',
  imports: [DatePipe, ReactiveFormsModule, Aviso, Dialogo, ZonaArchivos],
  templateUrl: './documentos-alumno.html',
  styleUrl: './documentos-alumno.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class DocumentosAlumno {
  private readonly api = inject(AlumnosApi);
  private readonly fb = inject(FormBuilder).nonNullable;

  readonly alumnoId = input.required<string>();
  readonly documentos = input.required<Documento[]>();
  readonly puedeEditar = input(false);

  /** Copia local: cambia al subir o eliminar sin volver a pedir la ficha. */
  protected readonly lista = linkedSignal(() => this.documentos());
  protected readonly op = new Operacion();
  protected readonly tiposArchivo = TIPOS_ARCHIVO;
  protected readonly subiendo = signal(false);
  protected readonly eliminando = signal<Documento | null>(null);
  protected readonly archivo = signal<File | null>(null);
  protected readonly form = this.fb.group({ tipo: ['', Validators.required] });

  protected texto(tipo: string): string {
    return TIPOS_ARCHIVO.find((t) => t.valor === tipo)?.texto ?? tipo;
  }

  protected tamano(bytes: number): string {
    return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }

  protected abrirSubir(): void {
    this.form.reset();
    this.archivo.set(null);
    this.op.abrir(() => this.subiendo.set(true));
  }

  protected elegir(archivos: File[]): void {
    this.archivo.set(archivos[0] ?? null);
  }

  protected subir(): void {
    const archivo = this.archivo();
    if (!archivo) return this.op.errorDialogo.set('Elige el archivo (PDF, JPG o PNG).');
    if (this.form.invalid) return this.op.errorDialogo.set('Elige qué tipo de documento es.');
    this.op.ejecutar(this.api.subirDocumento(this.alumnoId(), this.form.getRawValue().tipo, archivo), (d) => {
      this.subiendo.set(false);
      this.lista.update((l) => [d, ...l]);
      this.op.exito('Documento subido.');
    });
  }

  /** Descarga con el token (no es un enlace público) y la guarda con su nombre original. */
  protected descargar(d: Documento): void {
    this.op.ejecutar(this.api.descargarDocumento(this.alumnoId(), d.id), (blob) => {
      const enlace = document.createElement('a');
      enlace.href = URL.createObjectURL(blob);
      enlace.download = d.nombre_original;
      enlace.click();
      setTimeout(() => URL.revokeObjectURL(enlace.href), 1000);
    }, { enDialogo: false });
  }

  protected abrirEliminar(d: Documento): void {
    this.op.abrir(() => this.eliminando.set(d));
  }

  protected eliminar(): void {
    const d = this.eliminando();
    if (!d) return;
    this.op.ejecutar(this.api.eliminarDocumento(this.alumnoId(), d.id), () => {
      this.eliminando.set(null);
      this.lista.update((l) => l.filter((x) => x.id !== d.id));
      this.op.exito('Documento eliminado.');
    });
  }
}
