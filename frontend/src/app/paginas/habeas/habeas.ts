import { DatePipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Observable } from 'rxjs';

import { Aviso } from '../../compartido/aviso';
import { Dialogo } from '../../compartido/dialogo';
import { isoLocal } from '../../compartido/fechas';
import { Operacion } from '../../compartido/operacion';
import { Esquema } from '../../core/api/tipos';
import { API } from '../../core/modelos';

export type Solicitud = Esquema<'SolicitudOut'>;
const URL = `${API}/habeas`;
const url = (id: string) => `${URL}/${encodeURIComponent(id)}`;

/** Consultas y reclamos de los titulares sobre sus datos (Ley 1581), con su plazo legal en días hábiles. */
@Component({
  selector: 'app-habeas',
  imports: [DatePipe, ReactiveFormsModule, Aviso, Dialogo],
  templateUrl: './habeas.html',
  styleUrl: './habeas.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HabeasPage implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly fb = inject(FormBuilder).nonNullable;

  protected readonly op = new Operacion();
  protected readonly hoy = isoLocal(new Date());
  protected readonly solicitudes = signal<Solicitud[] | null>(null);
  protected readonly ver = signal<'en_tramite' | 'respondida'>('en_tramite');
  protected readonly lista = computed(() => (this.solicitudes() ?? []).filter((s) => s.estado === this.ver()));
  protected readonly conteo = computed(() => {
    const l = this.solicitudes() ?? [];
    return { tramite: l.filter((s) => s.estado === 'en_tramite').length, respondidas: l.filter((s) => s.estado === 'respondida').length };
  });

  protected readonly creando = signal(false);
  protected readonly respondiendo = signal<Solicitud | null>(null);
  protected readonly prorrogando = signal<Solicitud | null>(null);

  protected readonly formNueva = this.fb.group({
    tipo: this.fb.control<'consulta' | 'reclamo' | ''>('', Validators.required),
    titular: ['', [Validators.required, Validators.minLength(3), Validators.maxLength(120)]],
    contacto: ['', [Validators.required, Validators.minLength(5), Validators.maxLength(120)]],
    descripcion: ['', [Validators.required, Validators.minLength(10), Validators.maxLength(2000)]],
    recibida_el: [''],
  });
  protected readonly formRespuesta = this.fb.group({
    respuesta: ['', [Validators.required, Validators.minLength(10), Validators.maxLength(4000)]],
  });
  protected readonly formProrroga = this.fb.group({
    motivo: ['', [Validators.required, Validators.minLength(10), Validators.maxLength(500)]],
  });

  ngOnInit(): void {
    this.http.get<Solicitud[]>(URL).subscribe({
      next: (l) => this.solicitudes.set(l),
      error: (e: unknown) => this.op.error(e),
    });
  }

  /** ok / pronto (3 hábiles o menos) / vencida, para el color de los días restantes. */
  protected tono(s: Solicitud): string {
    if (s.dias_habiles_restantes < 0) return 'mal';
    return s.dias_habiles_restantes <= 3 ? 'pendiente' : 'ok';
  }

  protected abrirNueva(): void {
    this.formNueva.reset();
    this.op.abrir(() => this.creando.set(true));
  }

  protected registrar(): void {
    const f = this.formNueva.getRawValue();
    if (this.formNueva.invalid || !f.tipo) return this.op.errorDialogo.set('Completa el tipo, quién la hace, el contacto y la descripción.');
    const cuerpo: Esquema<'SolicitudIn'> = { ...f, tipo: f.tipo, recibida_el: f.recibida_el || null };
    this.guardar(this.http.post<Solicitud>(URL, cuerpo), () => this.creando.set(false), 'Solicitud registrada.');
  }

  protected abrirRespuesta(s: Solicitud): void {
    this.formRespuesta.reset();
    this.op.abrir(() => this.respondiendo.set(s));
  }

  protected responder(): void {
    const s = this.respondiendo();
    if (!s) return;
    if (this.formRespuesta.invalid) return this.op.errorDialogo.set('Escribe la respuesta (mínimo 10 caracteres).');
    this.guardar(this.http.post<Solicitud>(`${url(s.id)}/responder`, this.formRespuesta.getRawValue()),
      () => this.respondiendo.set(null), 'Respuesta registrada.');
  }

  protected abrirProrroga(s: Solicitud): void {
    this.formProrroga.reset();
    this.op.abrir(() => this.prorrogando.set(s));
  }

  protected prorrogar(): void {
    const s = this.prorrogando();
    if (!s) return;
    if (this.formProrroga.invalid) return this.op.errorDialogo.set('Escribe el motivo (mínimo 10 caracteres): se le informa al titular.');
    this.guardar(this.http.post<Solicitud>(`${url(s.id)}/prorrogar`, this.formProrroga.getRawValue()),
      () => this.prorrogando.set(null), 'Plazo ampliado.');
  }

  private guardar(peticion: Observable<Solicitud>, cerrar: () => void, texto: string): void {
    this.op.ejecutar(peticion, (s) => {
      cerrar();
      this.solicitudes.update((l) => [s, ...(l ?? []).filter((x) => x.id !== s.id)]);
      this.op.exito(texto);
    });
  }
}
