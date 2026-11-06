import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';

import { AuthService } from './auth/auth.service';
import { API } from './modelos';
import { seccionesVisibles } from './secciones';

export type Pose = 'saluda' | 'senala' | 'remata';

/** Un paso del recorrido. `objetivo`: valor de `data-tutorial` que se resalta (null = burbuja al centro). */
export interface PasoTutorial {
  objetivo: string | null;
  /** Ruta de la sección del paso: si la persona no la ve en su menú, el paso se salta. */
  seccion?: string;
  pose: Pose;
  titulo: string;
  texto: string;
}

/** Brasa, el dragón del club, presenta el panel. Corto a propósito: menos de un minuto. */
const PASOS: PasoTutorial[] = [
  {
    objetivo: null, pose: 'saluda', titulo: '¡Hola, {nombre}!',
    texto: 'Soy Brasa, el dragón del club. Te muestro el panel en un minuto. Puedes saltarlo cuando quieras.',
  },
  {
    objetivo: 'seccion:', seccion: '', pose: 'senala', titulo: 'Resumen',
    texto: 'Lo importante de hoy: alertas que piden tu decisión, el entrenamiento del día y lo que falta por cobrar.',
  },
  {
    objetivo: 'seccion:alumnos', seccion: 'alumnos', pose: 'senala', titulo: 'Alumnos',
    texto: 'Fichas de los alumnos con sus acudientes, documentos e inscripción. Cada uno tiene su código, como F012.',
  },
  {
    objetivo: 'seccion:asistencia', seccion: 'asistencia', pose: 'senala', titulo: 'Asistencia',
    texto: 'Marca quién vino a entrenar. Quien no marca ni avisa recibe su multa al cierre del día.',
  },
  {
    objetivo: 'seccion:torneos', seccion: 'torneos', pose: 'senala', titulo: 'Torneos',
    texto: 'Los torneos del club: clubes inscritos, cupos, pagos y el flyer que se ve en el sitio.',
  },
  {
    objetivo: 'seccion:perfil-club', seccion: 'perfil-club', pose: 'senala', titulo: 'Perfil del club',
    texto: 'Todo lo que se ve en el sitio público: galería, entrenadores y torneos realizados.',
  },
  {
    objetivo: 'ayuda', pose: 'senala', titulo: '¿Dudas?',
    texto: 'Este botón explica cada pantalla. Desde ahí también puedes volver a ver este recorrido.',
  },
  {
    objetivo: null, pose: 'remata', titulo: '¡A jugar!',
    texto: 'Ya conoces la cancha. A rematar.',
  },
];

/**
 * Tutorial guiado del panel. Sale solo la primera vez que una cuenta del staff entra (lo guarda el servidor, no el
 * navegador: no se repite en otro dispositivo) y se puede volver a ver desde la ayuda.
 */
@Injectable({ providedIn: 'root' })
export class TutorialService {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);

  readonly activo = signal(false);
  readonly indice = signal(0);

  /** Pasos que aplican a esta persona: nunca le muestra una sección que no tiene en su menú. */
  readonly pasos = computed<PasoTutorial[]>(() => {
    const u = this.auth.usuario();
    if (!u) return [];
    const rutas = new Set(seccionesVisibles((p) => this.auth.tieneAlguno(p)).map((s) => s.ruta));
    const nombre = u.nombre.trim().split(/\s+/)[0] ?? '';
    return PASOS.filter((p) => p.seccion === undefined || rutas.has(p.seccion))
      .map((p) => ({ ...p, titulo: p.titulo.replace('{nombre}', nombre) }));
  });

  readonly paso = computed(() => this.pasos()[this.indice()] ?? null);

  /** El staff que nunca lo vio. Las familias (Miembro) tienen otro panel, más simple: no les sale. */
  debeMostrarse(): boolean {
    const u = this.auth.usuario();
    return !!u && !u.tutorial_visto && u.rol !== 'MIEMBRO';
  }

  iniciar(): void {
    this.indice.set(0);
    this.activo.set(true);
  }

  siguiente(): void {
    if (this.indice() < this.pasos().length - 1) this.indice.update((i) => i + 1);
    else this.terminar();
  }

  anterior(): void {
    this.indice.update((i) => Math.max(0, i - 1));
  }

  /** Al terminar o saltarlo: queda visto en el servidor para esta cuenta. */
  terminar(): void {
    this.activo.set(false);
    const u = this.auth.usuario();
    if (!u || u.tutorial_visto) return;
    this.auth.usuario.set({ ...u, tutorial_visto: true });
    this.http.post(`${API}/auth/tutorial`, {}).subscribe({ error: () => undefined }); // si falla, sale otra vez
  }
}
