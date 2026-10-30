import { DatePipe } from '@angular/common';
import { HttpClient, HttpParams } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';

import { Aviso } from '../../compartido/aviso';
import { mensajeError } from '../../compartido/errores';
import { API } from '../../core/modelos';

interface AvisoWhatsApp {
  id: string;
  tipo: string;
  titulo: string;
  telefono: string;
  mensaje: string;
  enlace: string;
  creado_en: string;
}

interface Correo {
  id: string;
  tipo: string;
  titulo: string;
  email: string; // enmascarado
  estado: 'pendiente' | 'enviado' | 'fallido';
  intentos: number;
  error: string | null;
  creado_en: string;
}

const TIPOS: Record<string, string> = {
  recordatorio_inscripcion: 'Recordatorio de pago',
  inscripcion_vencida: 'Inscripción vencida',
  multa: 'Multa',
  justificacion: 'Justificación',
  alerta_inasistencia: 'Inasistencias',
  aviso_mora: 'Aviso de mora',
  mora: 'En mora',
  fin_mora: 'Salió de la mora',
  mora_staff: 'Mora (staff)',
};

/** Solo se abren enlaces de WhatsApp (el servidor los arma; esto es una segunda barrera). */
const ENLACE_WA = /^https:\/\/wa\.me\/\d{8,15}\?text=/;

@Component({
  selector: 'app-avisos',
  imports: [DatePipe, Aviso],
  templateUrl: './avisos.html',
  styleUrl: './avisos.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AvisosPage implements OnInit {
  private readonly http = inject(HttpClient);

  protected readonly tipos = TIPOS;
  protected readonly vista = signal<'whatsapp' | 'correos'>('whatsapp');
  protected readonly cola = signal<AvisoWhatsApp[] | null>(null);
  protected readonly correos = signal<Correo[] | null>(null);
  protected readonly filtroCorreo = signal<'' | Correo['estado']>('');
  /** Avisos cuyo WhatsApp ya se abrió: falta confirmar si se envió. */
  protected readonly abiertos = signal<Set<string>>(new Set());
  protected readonly errorCarga = signal(false);
  protected readonly mensaje = signal<{ error: boolean; texto: string } | null>(null);
  protected readonly ocupado = signal<string | null>(null);

  ngOnInit(): void {
    this.cargarCola();
  }

  protected cambiarVista(v: 'whatsapp' | 'correos'): void {
    this.vista.set(v);
    if (v === 'correos' && this.correos() === null) this.cargarCorreos();
  }

  private cargarCola(): void {
    this.http.get<AvisoWhatsApp[]>(`${API}/notificaciones/whatsapp`).subscribe({
      next: (c) => {
        this.errorCarga.set(false);
        this.cola.set(c);
      },
      error: () => this.errorCarga.set(true),
    });
  }

  protected cargarCorreos(): void {
    this.correos.set(null);
    let params = new HttpParams();
    if (this.filtroCorreo()) params = params.set('estado', this.filtroCorreo());
    this.http.get<Correo[]>(`${API}/notificaciones/correos`, { params }).subscribe({
      next: (c) => this.correos.set(c),
      error: () => this.errorCarga.set(true),
    });
  }

  protected filtrarCorreos(e: '' | Correo['estado']): void {
    this.filtroCorreo.set(e);
    this.cargarCorreos();
  }

  protected enlaceSeguro(a: AvisoWhatsApp): string | null {
    return ENLACE_WA.test(a.enlace) ? a.enlace : null;
  }

  protected abierto(a: AvisoWhatsApp): boolean {
    return this.abiertos().has(a.id);
  }

  /** Al abrir WhatsApp se pide confirmar si de verdad se envió. */
  protected alAbrir(a: AvisoWhatsApp): void {
    this.abiertos.update((s) => new Set(s).add(a.id));
  }

  protected marcar(a: AvisoWhatsApp, accion: 'enviado' | 'descartado'): void {
    this.ocupado.set(a.id);
    this.mensaje.set(null);
    this.http.post(`${API}/notificaciones/${encodeURIComponent(a.id)}/whatsapp`, { accion }).subscribe({
      next: () => {
        this.ocupado.set(null);
        this.cola.update((c) => c?.filter((x) => x.id !== a.id) ?? c);
        this.mensaje.set({ error: false, texto: accion === 'enviado' ? 'Marcado como enviado.' : 'Aviso descartado.' });
      },
      error: (e) => {
        this.ocupado.set(null);
        this.mensaje.set({ error: true, texto: mensajeError(e) });
      },
    });
  }
}
