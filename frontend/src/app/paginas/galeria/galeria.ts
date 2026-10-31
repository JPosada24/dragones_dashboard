import { DatePipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import {
  ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, effect, inject, input, signal,
} from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { Observable } from 'rxjs';

import { Aviso } from '../../compartido/aviso';
import { AlbumClub, FotoClub, VideoClub, miniaturaYoutube } from '../../compartido/club';
import { Dialogo } from '../../compartido/dialogo';
import { mensajeError } from '../../compartido/errores';
import { PESTANAS_CLUB, Pestanas } from '../../compartido/pestanas';
import { ZonaArchivos } from '../../compartido/zona-archivos';
import { API } from '../../core/modelos';

const URL_CLUB = `${API}/club`;

/** Galería del sitio: álbumes (cada uno con sus fotos) y videos de YouTube. */
@Component({
  selector: 'app-galeria',
  imports: [ReactiveFormsModule, DatePipe, RouterLink, Aviso, Dialogo, Pestanas, ZonaArchivos],
  templateUrl: './galeria.html',
  styleUrl: './galeria.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GaleriaPage implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly fb = inject(FormBuilder).nonNullable;

  /** Álbum abierto (?album=…); sin él se ve la lista de álbumes. */
  readonly album = input<string>();

  protected readonly pestanas = PESTANAS_CLUB;
  protected readonly miniaturaYoutube = miniaturaYoutube;

  protected readonly albumes = signal<AlbumClub[] | null>(null);
  protected readonly videos = signal<VideoClub[]>([]);
  protected readonly errorCarga = signal(false);
  protected readonly mensaje = signal<{ error: boolean; texto: string } | null>(null);
  protected readonly errorDialogo = signal<string | null>(null);
  protected readonly ocupado = signal(false);
  /** Miniaturas (blob:, pedidas con el token: un álbum sin publicar no es público). */
  protected readonly miniaturas = signal<Record<string, string>>({});
  /** Portadas propias de los álbumes (blob:), por "id:versión". */
  protected readonly portadas = signal<Record<string, string>>({});
  /** Fotos marcadas en el álbum abierto. */
  protected readonly seleccion = signal<ReadonlySet<string>>(new Set());

  protected readonly abierto = computed(() => {
    const id = this.album();
    return id ? (this.albumes()?.find((a) => a.id === id) ?? null) : null;
  });
  protected readonly todasMarcadas = computed(() => {
    const a = this.abierto();
    return !!a && a.fotos.length > 0 && this.seleccion().size === a.fotos.length;
  });

  // Ventanas
  protected readonly editandoAlbum = signal<AlbumClub | 'nuevo' | null>(null);
  protected readonly subiendo = signal(false);
  protected readonly eligiendoPortada = signal(false);
  protected archivoPortada: File | null = null;
  protected readonly progreso = signal<string | null>(null);
  protected readonly creandoVideo = signal(false);
  protected readonly confirmando = signal<{ titulo: string; texto: string; boton: string; accion: () => void } | null>(null);

  protected readonly formAlbum = this.fb.group({
    nombre: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(120)]],
    fecha: [''],
    publicado: false,
  });
  protected readonly formFotos = this.fb.group({ autorizacion: false });
  protected archivos: File[] = [];
  protected readonly formVideo = this.fb.group({
    titulo: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(120)]],
    enlace: ['', [Validators.required, Validators.minLength(10)]],
  });

  constructor() {
    inject(DestroyRef).onDestroy(() => {
      Object.values(this.miniaturas()).forEach((u) => URL.revokeObjectURL(u));
      Object.values(this.portadas()).forEach((u) => URL.revokeObjectURL(u));
    });
    // Al cambiar de vista: en la lista solo hacen falta las portadas; dentro del álbum, todas sus fotos.
    effect(() => {
      const lista = this.albumes();
      if (!lista) return;
      const a = this.abierto();
      // Portada propia si la hay; si no, la primera foto.
      this.cargarPortadas(a ? [a] : lista);
      this.cargarMiniaturas(a ? a.fotos : lista.filter((x) => !x.portada).flatMap((x) => x.fotos.slice(0, 1)));
    });
    effect(() => {
      this.album();
      this.seleccion.set(new Set());
    });
  }

  ngOnInit(): void {
    this.http.get<AlbumClub[]>(`${URL_CLUB}/albumes`).subscribe({
      next: (l) => this.albumes.set(l),
      error: () => this.errorCarga.set(true),
    });
    this.http.get<VideoClub[]>(`${URL_CLUB}/videos`).subscribe({ next: (v) => this.videos.set(v) });
  }

  private cargarMiniaturas(fotos: FotoClub[]): void {
    for (const f of fotos) {
      if (this.miniaturas()[f.id]) continue;
      this.http.get(`${URL_CLUB}/fotos/${encodeURIComponent(f.id)}?tam=mini`, { responseType: 'blob' }).subscribe({
        next: (blob) => this.miniaturas.update((m) => ({ ...m, [f.id]: URL.createObjectURL(blob) })),
      });
    }
  }

  private cargarPortadas(lista: AlbumClub[]): void {
    for (const a of lista) {
      const clave = `${a.id}:${a.portada}`;
      if (!a.portada || this.portadas()[clave]) continue;
      this.http.get(`${URL_CLUB}/albumes/${encodeURIComponent(a.id)}/portada`, { responseType: 'blob' }).subscribe({
        next: (blob) => this.portadas.update((p) => ({ ...p, [clave]: URL.createObjectURL(blob) })),
      });
    }
  }

  /** Portada propia del álbum si la tiene; si no, su primera foto. */
  protected portada(a: AlbumClub): string | null {
    if (a.portada) return this.portadas()[`${a.id}:${a.portada}`] ?? null;
    const f = a.fotos[0];
    return f ? (this.miniaturas()[f.id] ?? null) : null;
  }

  // ---------- Portada propia (no es una foto del álbum) ----------
  protected abrirPortada(): void {
    this.formFotos.reset();
    this.archivoPortada = null;
    this.abrirVentana(() => this.eligiendoPortada.set(true));
  }

  protected elegirPortada(archivos: File[]): void {
    this.archivoPortada = archivos[0] ?? null;
  }

  protected guardarPortada(): void {
    const a = this.abierto();
    if (!a) return;
    if (!this.archivoPortada) return this.errorDialogo.set('Elige o arrastra la foto de la portada.');
    if (!this.formFotos.getRawValue().autorizacion) {
      return this.errorDialogo.set('Confirma que tienes autorización de los acudientes.');
    }
    const datos = new FormData();
    datos.append('archivo', this.archivoPortada);
    datos.append('autorizacion', 'true');
    this.ejecutar(this.http.post<AlbumClub>(`${URL_CLUB}/albumes/${encodeURIComponent(a.id)}/portada`, datos), (nuevo) => {
      this.reemplazar(nuevo);
      this.eligiendoPortada.set(false);
      this.exito(`Portada de «${nuevo.nombre}» actualizada.`);
    });
  }

  protected quitarPortada(a: AlbumClub): void {
    this.ejecutar(this.http.delete<AlbumClub>(`${URL_CLUB}/albumes/${encodeURIComponent(a.id)}/portada`), (nuevo) => {
      this.reemplazar(nuevo);
      this.exito('Se quitó la portada: ahora se usa la primera foto del álbum.');
    }, false);
  }


  private ejecutar<T>(peticion: Observable<T>, ok: (r: T) => void, enDialogo = true): void {
    this.ocupado.set(true);
    this.errorDialogo.set(null);
    if (!enDialogo) this.mensaje.set(null);
    peticion.subscribe({
      next: (r) => {
        this.ocupado.set(false);
        ok(r);
      },
      error: (e) => {
        this.ocupado.set(false);
        if (enDialogo) this.errorDialogo.set(mensajeError(e));
        else this.mensaje.set({ error: true, texto: mensajeError(e) });
      },
    });
  }

  private exito(texto: string): void {
    this.mensaje.set({ error: false, texto });
  }

  private abrirVentana(accion: () => void): void {
    this.errorDialogo.set(null);
    this.mensaje.set(null);
    accion();
  }

  private reemplazar(a: AlbumClub): void {
    this.albumes.update((l) => (l ?? []).map((x) => (x.id === a.id ? a : x)));
  }

  // ---------- Álbumes ----------
  protected abrirEditarAlbum(a: AlbumClub | 'nuevo'): void {
    this.formAlbum.reset(a === 'nuevo' ? undefined : { nombre: a.nombre, fecha: a.fecha ?? '', publicado: a.publicado });
    this.abrirVentana(() => this.editandoAlbum.set(a));
  }

  protected guardarAlbum(): void {
    const a = this.editandoAlbum();
    if (!a) return;
    if (this.formAlbum.invalid) return this.errorDialogo.set('Escribe el nombre del álbum.');
    const f = this.formAlbum.getRawValue();
    const cuerpo = { nombre: f.nombre.trim(), fecha: f.fecha || null, publicado: f.publicado };
    if (a === 'nuevo') {
      this.ejecutar(this.http.post<AlbumClub>(`${URL_CLUB}/albumes`, cuerpo), (nuevo) => {
        this.albumes.update((l) => [nuevo, ...(l ?? [])]);
        this.editandoAlbum.set(null);
        void this.router.navigate([], { queryParams: { album: nuevo.id } }); // directo a subirle fotos
        this.exito(`Álbum «${nuevo.nombre}» creado. Ahora súbele fotos.`);
      });
    } else {
      this.ejecutar(this.http.patch<AlbumClub>(`${URL_CLUB}/albumes/${encodeURIComponent(a.id)}`, cuerpo), (nuevo) => {
        this.reemplazar(nuevo);
        this.editandoAlbum.set(null);
        this.exito('Álbum actualizado.');
      });
    }
  }

  protected cambiarPublicado(a: AlbumClub): void {
    this.ejecutar(this.http.patch<AlbumClub>(`${URL_CLUB}/albumes/${encodeURIComponent(a.id)}`, { publicado: !a.publicado }),
      (nuevo) => {
        this.reemplazar(nuevo);
        this.exito(nuevo.publicado ? `«${nuevo.nombre}» ya se ve en el sitio.` : `«${nuevo.nombre}» quedó oculto.`);
      }, false);
  }

  protected eliminarAlbum(a: AlbumClub): void {
    this.confirmar('Eliminar álbum', `Se borra «${a.nombre}» con sus ${a.fotos.length} fotos. No se puede deshacer.`, 'Eliminar álbum', () =>
      this.ejecutar(this.http.delete(`${URL_CLUB}/albumes/${encodeURIComponent(a.id)}`), () => {
        this.albumes.update((l) => (l ?? []).filter((x) => x.id !== a.id));
        this.confirmando.set(null);
        void this.router.navigate([], { queryParams: {} });
        this.exito('Álbum eliminado.');
      }));
  }

  // ---------- Fotos ----------
  protected abrirSubir(): void {
    this.formFotos.reset();
    this.archivos = [];
    this.progreso.set(null);
    this.abrirVentana(() => this.subiendo.set(true));
  }

  protected elegirArchivos(archivos: File[]): void {
    this.archivos = archivos;
  }

  /** Sube las fotos una por una (así una que falle no tumba las demás y se ve el avance). */
  protected subirFotos(): void {
    const a = this.abierto();
    if (!a) return;
    if (!this.archivos.length) return this.errorDialogo.set('Elige al menos una foto.');
    if (!this.formFotos.getRawValue().autorizacion) {
      return this.errorDialogo.set('Confirma que tienes autorización de los acudientes.');
    }
    const pendientes = [...this.archivos];
    const total = pendientes.length;
    const fallidas: string[] = [];
    let subidas = 0;
    this.ocupado.set(true);
    this.errorDialogo.set(null);
    const siguiente = (): void => {
      const archivo = pendientes.shift();
      if (!archivo) {
        this.ocupado.set(false);
        this.progreso.set(null);
        if (fallidas.length) {
          this.errorDialogo.set(`Se subieron ${subidas} de ${total}. No se pudieron subir: ${fallidas.join(', ')}.`);
        } else {
          this.subiendo.set(false);
          this.exito(`${subidas} ${subidas === 1 ? 'foto subida' : 'fotos subidas'} a «${a.nombre}».`);
        }
        return;
      }
      this.progreso.set(`Subiendo ${total - pendientes.length} de ${total}…`);
      const datos = new FormData();
      datos.append('archivo', archivo);
      datos.append('autorizacion', 'true');
      this.http.post<FotoClub>(`${URL_CLUB}/albumes/${encodeURIComponent(a.id)}/fotos`, datos).subscribe({
        next: (foto) => {
          subidas++;
          this.albumes.update((l) => (l ?? []).map((x) => (x.id === a.id ? { ...x, fotos: [...x.fotos, foto] } : x)));
          siguiente();
        },
        error: () => {
          fallidas.push(archivo.name);
          siguiente();
        },
      });
    };
    siguiente();
  }

  protected marcada(f: FotoClub): boolean {
    return this.seleccion().has(f.id);
  }

  protected marcar(f: FotoClub): void {
    this.seleccion.update((s) => {
      const nueva = new Set(s);
      if (nueva.has(f.id)) nueva.delete(f.id);
      else nueva.add(f.id);
      return nueva;
    });
  }

  protected marcarTodas(): void {
    const a = this.abierto();
    if (!a) return;
    this.seleccion.set(this.todasMarcadas() ? new Set() : new Set(a.fotos.map((f) => f.id)));
  }

  protected eliminarSeleccionadas(): void {
    const a = this.abierto();
    const ids = [...this.seleccion()];
    if (!a || !ids.length) return;
    const n = ids.length;
    this.confirmar('Eliminar fotos', `Se borran ${n} ${n === 1 ? 'foto' : 'fotos'} de «${a.nombre}» y del sitio. No se puede deshacer.`,
      `Eliminar ${n}`, () =>
        this.ejecutar(this.http.post<{ eliminadas: number }>(`${URL_CLUB}/fotos/eliminar`, { ids }), (r) => {
          const quitar = new Set(ids);
          this.albumes.update((l) => (l ?? []).map((x) => (x.id === a.id ? { ...x, fotos: x.fotos.filter((f) => !quitar.has(f.id)) } : x)));
          ids.forEach((id) => {
            const url = this.miniaturas()[id];
            if (url) URL.revokeObjectURL(url);
          });
          this.seleccion.set(new Set());
          this.confirmando.set(null);
          this.exito(`${r.eliminadas} ${r.eliminadas === 1 ? 'foto eliminada' : 'fotos eliminadas'}.`);
        }));
  }

  // ---------- Videos ----------
  protected abrirVideo(): void {
    this.formVideo.reset();
    this.abrirVentana(() => this.creandoVideo.set(true));
  }

  protected crearVideo(): void {
    if (this.formVideo.invalid) return this.errorDialogo.set('Escribe el título y pega el enlace de YouTube.');
    this.ejecutar(this.http.post<VideoClub>(`${URL_CLUB}/videos`, this.formVideo.getRawValue()), (v) => {
      this.videos.update((l) => [v, ...l]);
      this.creandoVideo.set(false);
      this.exito(`Video «${v.titulo}» agregado.`);
    });
  }

  protected cambiarVideo(v: VideoClub): void {
    this.ejecutar(this.http.patch<VideoClub>(`${URL_CLUB}/videos/${encodeURIComponent(v.id)}`, { publicado: !v.publicado }),
      (nuevo) => {
        this.videos.update((l) => l.map((x) => (x.id === v.id ? nuevo : x)));
        this.exito(nuevo.publicado ? 'Video publicado.' : 'Video oculto.');
      }, false);
  }

  protected eliminarVideo(v: VideoClub): void {
    this.confirmar('Eliminar video', `Se quita «${v.titulo}» del sitio (en YouTube sigue igual).`, 'Eliminar', () =>
      this.ejecutar(this.http.delete(`${URL_CLUB}/videos/${encodeURIComponent(v.id)}`), () => {
        this.videos.update((l) => l.filter((x) => x.id !== v.id));
        this.confirmando.set(null);
        this.exito('Video eliminado.');
      }));
  }

  private confirmar(titulo: string, texto: string, boton: string, accion: () => void): void {
    this.abrirVentana(() => this.confirmando.set({ titulo, texto, boton, accion }));
  }
}
