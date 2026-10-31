import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Title } from '@angular/platform-browser';
import { RouterLink } from '@angular/router';

import {
  AlbumClub, FotoClub, IntegranteClub, PerfilClub, VideoClub, enlaceYoutube, iniciales, miniaturaYoutube,
} from '../../compartido/club';
import { Dialogo } from '../../compartido/dialogo';
import { mensajeError } from '../../compartido/errores';
import { formatoFecha } from '../../compartido/fechas';
import { PesosPipe } from '../../compartido/pesos.pipe';
import { numeroWhatsApp } from '../../compartido/whatsapp';
import { API } from '../../core/modelos';

interface DiaHorario {
  dia_semana: number;
  hora_inicio: string;
  hora_fin: string;
  lugar: string | null;
}

interface TorneoAbierto {
  id: string;
  nombre: string;
  rama: string;
  fecha_inicio: string;
  fecha_fin: string;
  fecha_limite_inscripcion: string;
  lugar: string | null;
  valor_inscripcion: number;
  cupos_libres: number;
}

interface Sitio {
  perfil: PerfilClub;
  horario: DiaHorario[];
  albumes: AlbumClub[];
  videos: VideoClub[];
  equipo: IntegranteClub[];
  torneos: TorneoAbierto[];
}

const DIAS = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo'];
const RAMAS: Record<string, string> = { femenina: 'Femenina', masculina: 'Masculina', mixta: 'Mixta' };
const PUBLICO = `${API}/publico`;

/** Sitio público del club: se ve sin cuenta. Todo el texto viene de la API y se muestra como texto plano. */
@Component({
  selector: 'app-sitio',
  imports: [ReactiveFormsModule, RouterLink, Dialogo, PesosPipe],
  templateUrl: './sitio.html',
  styleUrl: './sitio.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SitioPage implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly titulo = inject(Title);
  private readonly fb = inject(FormBuilder).nonNullable;

  protected readonly dias = DIAS;
  protected readonly ramas = RAMAS;
  protected readonly iniciales = iniciales;
  protected readonly miniaturaYoutube = miniaturaYoutube;
  protected readonly enlaceYoutube = enlaceYoutube;
  protected readonly formatoFecha = formatoFecha;

  protected readonly sitio = signal<Sitio | null>(null);
  protected readonly estado = signal<'cargando' | 'listo' | 'no_publicado' | 'error'>('cargando');
  protected readonly ampliada = signal<{ album: AlbumClub; indice: number } | null>(null);
  protected readonly inscribiendo = signal<TorneoAbierto | null>(null);
  protected readonly enviando = signal(false);
  protected readonly errorFormulario = signal<string | null>(null);
  protected readonly resultado = signal<string | null>(null);

  protected readonly whatsapp = computed(() => {
    const p = this.sitio()?.perfil;
    const numero = numeroWhatsApp(p?.whatsapp ?? null);
    return numero ? `https://wa.me/${numero}?text=${encodeURIComponent(`Hola, quiero información sobre ${p?.nombre ?? 'el club'}.`)}` : null;
  });
  protected readonly instagram = computed(() => {
    const u = this.sitio()?.perfil.instagram;
    return u ? `https://www.instagram.com/${encodeURIComponent(u)}/` : null;
  });
  protected readonly facebook = computed(() => {
    const u = this.sitio()?.perfil.facebook;
    return u ? `https://www.facebook.com/${encodeURIComponent(u)}` : null;
  });
  protected readonly fotoAmpliada = computed<FotoClub | null>(() => {
    const a = this.ampliada();
    return a ? (a.album.fotos[a.indice] ?? null) : null;
  });

  protected readonly form = this.fb.group({
    nombre_club: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(120)]],
    ciudad: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(80)]],
    delegado_nombre: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(120)]],
    delegado_telefono: ['', [Validators.required, Validators.pattern(/^\+?[\d\s-]{7,20}$/)]],
    delegado_email: ['', Validators.email],
    acepta_datos: [false, Validators.requiredTrue],
    sitio_web: [''], // trampa para bots: oculta para las personas
  });

  ngOnInit(): void {
    this.http.get<Sitio>(`${PUBLICO}/club`).subscribe({
      next: (s) => {
        this.sitio.set(s);
        this.estado.set('listo');
        this.titulo.setTitle(s.perfil.nombre);
      },
      error: (e: unknown) => this.estado.set(e instanceof HttpErrorResponse && e.status === 404 ? 'no_publicado' : 'error'),
    });
  }

  protected foto(f: FotoClub, tam: 'mini' | 'grande'): string {
    return `${PUBLICO}/fotos/${encodeURIComponent(f.id)}?tam=${tam}`;
  }

  protected hora(h: string): string {
    const [hh = 0, mm = 0] = h.split(':').map(Number);
    return `${hh % 12 || 12}:${String(mm).padStart(2, '0')} ${hh < 12 ? 'am' : 'pm'}`;
  }

  protected ampliar(album: AlbumClub, indice: number): void {
    this.ampliada.set({ album, indice });
  }

  protected mover(paso: number): void {
    this.ampliada.update((a) => {
      if (!a) return a;
      const total = a.album.fotos.length;
      return { ...a, indice: (a.indice + paso + total) % total };
    });
  }

  protected abrirInscripcion(t: TorneoAbierto): void {
    this.form.reset();
    this.errorFormulario.set(null);
    this.resultado.set(null);
    this.inscribiendo.set(t);
  }

  protected inscribir(): void {
    const t = this.inscribiendo();
    if (!t) return;
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return this.errorFormulario.set(this.form.controls.acepta_datos.invalid
        ? 'Debes autorizar el tratamiento de los datos para inscribirte.'
        : 'Revisa los datos: nombre del club, ciudad, delegado y un teléfono válido.');
    }
    const f = this.form.getRawValue();
    const cuerpo = {
      nombre_club: f.nombre_club.trim(), ciudad: f.ciudad.trim(), delegado_nombre: f.delegado_nombre.trim(),
      delegado_telefono: f.delegado_telefono.replace(/[\s-]/g, ''), delegado_email: f.delegado_email.trim() || null,
      acepta_datos: true, sitio_web: f.sitio_web || null,
    };
    this.enviando.set(true);
    this.errorFormulario.set(null);
    this.http.post<{ estado: string; mensaje: string }>(`${PUBLICO}/torneos/${encodeURIComponent(t.id)}/inscripcion`, cuerpo)
      .subscribe({
        next: (r) => {
          this.enviando.set(false);
          this.resultado.set(r.mensaje);
        },
        error: (e) => {
          this.enviando.set(false);
          this.errorFormulario.set(mensajeError(e));
        },
      });
  }
}
