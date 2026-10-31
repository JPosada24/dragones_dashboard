import { HttpClient } from '@angular/common/http';
import {
  ChangeDetectionStrategy, Component, ElementRef, OnInit, computed, inject, signal, viewChild,
} from '@angular/core';
import { FormsModule } from '@angular/forms';

import { Aviso } from '../../compartido/aviso';
import { mensajeError } from '../../compartido/errores';
import { AuthService } from '../../core/auth/auth.service';
import { API } from '../../core/modelos';

interface Mensaje {
  rol: 'user' | 'assistant';
  texto: string;
  herramientas?: string[];
}

interface EstadoAgente {
  configurado: boolean;
  limite_diario: number;
  usados_hoy: number;
}

interface Respuesta {
  texto: string;
  herramientas: string[];
  restantes_hoy: number;
}

/** Cuántos mensajes previos se reenvían (el servidor acepta hasta 20). */
const MAX_HISTORIAL = 20;

const HERRAMIENTAS: Record<string, string> = {
  buscar_alumnos: 'alumnos',
  estado_de_cuenta: 'estado de cuenta',
  asistencia_de_alumno: 'asistencia',
  multas: 'multas',
  inscripciones: 'inscripciones',
  entrenamientos: 'entrenamientos',
  rifas: 'rifas',
  resumen_del_club: 'resumen del club',
  riesgo_de_mora: 'mora',
  alertas_de_inasistencia: 'rachas de inasistencia',
  torneos: 'torneos',
};

const SUGERENCIAS_STAFF = [
  '¿Quiénes tienen multas pendientes y cuánto suman?',
  '¿Qué inscripciones vencen esta semana?',
  '¿Quién está en riesgo de mora?',
  '¿Cuántos talonarios faltan por pagar en la rifa actual?',
];
const SUGERENCIAS_FAMILIA = [
  '¿Mi hijo está a paz y salvo?',
  '¿Cuándo es el próximo entrenamiento?',
  '¿Cuántas veces ha faltado este mes?',
];

@Component({
  selector: 'app-asistente',
  imports: [FormsModule, Aviso],
  templateUrl: './asistente.html',
  styleUrl: './asistente.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AsistentePage implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private readonly lista = viewChild<ElementRef<HTMLElement>>('lista');

  /** La conversación vive solo en memoria: se borra al recargar (puede traer datos de menores). */
  protected readonly mensajes = signal<Mensaje[]>([]);
  protected readonly estado = signal<EstadoAgente | null>(null);
  protected readonly restantes = signal<number | null>(null);
  protected readonly pensando = signal(false);
  protected readonly error = signal<string | null>(null);
  protected borrador = '';

  protected readonly sugerencias = computed(() =>
    this.auth.tiene('alumnos.ver_todos') ? SUGERENCIAS_STAFF : SUGERENCIAS_FAMILIA);
  protected readonly disponible = computed(() => {
    const e = this.estado();
    return !!e && e.configurado && e.limite_diario > 0;
  });

  ngOnInit(): void {
    this.http.get<EstadoAgente>(`${API}/agente/estado`).subscribe({
      next: (e) => {
        this.estado.set(e);
        this.restantes.set(Math.max(0, e.limite_diario - e.usados_hoy));
      },
      error: (e) => this.error.set(mensajeError(e)),
    });
  }

  protected etiqueta(h: string): string {
    return HERRAMIENTAS[h] ?? h;
  }

  protected consultadas(m: Mensaje): string {
    return [...new Set((m.herramientas ?? []).map((h) => this.etiqueta(h)))].join(', ');
  }

  protected teclado(e: KeyboardEvent): void {
    // Enter envía; Shift+Enter hace un salto de línea.
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      this.enviar();
    }
  }

  protected usar(sugerencia: string): void {
    this.borrador = sugerencia;
    this.enviar();
  }

  protected enviar(): void {
    const pregunta = this.borrador.trim();
    if (!pregunta || this.pensando() || !this.disponible()) return;
    const historial = this.historialParaEnviar();
    this.error.set(null);
    this.borrador = '';
    this.mensajes.update((l) => [...l, { rol: 'user', texto: pregunta }]);
    this.pensando.set(true);
    this.bajar();
    this.http.post<Respuesta>(`${API}/agente/preguntar`, { pregunta, historial }).subscribe({
      next: (r) => {
        this.pensando.set(false);
        this.restantes.set(r.restantes_hoy);
        this.mensajes.update((l) => [...l, { rol: 'assistant', texto: r.texto, herramientas: r.herramientas }]);
        this.bajar();
      },
      error: (e) => {
        // La pregunta no quedó respondida: se quita y vuelve al cuadro de texto para reintentar.
        this.pensando.set(false);
        this.mensajes.update((l) => l.slice(0, -1));
        this.borrador = pregunta;
        this.error.set(mensajeError(e));
      },
    });
  }

  protected nueva(): void {
    this.mensajes.set([]);
    this.error.set(null);
  }

  /** Últimos mensajes, empezando siempre por uno del usuario (lo exige el servidor). */
  private historialParaEnviar(): { rol: string; texto: string }[] {
    let previos = this.mensajes().slice(-MAX_HISTORIAL);
    while (previos.length && previos[0]?.rol !== 'user') previos = previos.slice(1);
    return previos.map((m) => ({ rol: m.rol, texto: m.texto.slice(0, 6000) }));
  }

  private bajar(): void {
    queueMicrotask(() => {
      const el = this.lista()?.nativeElement;
      if (el) el.scrollTop = el.scrollHeight;
    });
  }
}
