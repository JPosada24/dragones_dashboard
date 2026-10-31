import { DatePipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Observable } from 'rxjs';

import { Aviso } from '../../compartido/aviso';
import {
  AlbumClub, FotoClub, IntegranteClub, PerfilClub, VideoClub, iniciales, miniaturaYoutube,
} from '../../compartido/club';
import { Dialogo } from '../../compartido/dialogo';
import { mensajeError } from '../../compartido/errores';
import { API } from '../../core/modelos';

interface Panel {
  perfil: PerfilClub;
  albumes: AlbumClub[];
  videos: VideoClub[];
  equipo: IntegranteClub[];
}

type Texto = 'mision' | 'vision' | 'historia';

const TEXTOS: { campo: Texto; titulo: string; vacio: string }[] = [
  { campo: 'mision', titulo: 'Misión', vacio: 'Para qué existe el club.' },
  { campo: 'vision', titulo: 'Visión', vacio: 'Hacia dónde quiere llegar.' },
  { campo: 'historia', titulo: 'Historia', vacio: 'Cómo nació y qué ha logrado.' },
];

const URL_CLUB = `${API}/club`;

@Component({
  selector: 'app-perfil-club',
  imports: [ReactiveFormsModule, DatePipe, RouterLink, Aviso, Dialogo],
  templateUrl: './perfil-club.html',
  styleUrl: './perfil-club.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PerfilClubPage implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly fb = inject(FormBuilder).nonNullable;

  protected readonly textos = TEXTOS;
  protected readonly iniciales = iniciales;
  protected readonly miniaturaYoutube = miniaturaYoutube;

  protected readonly panel = signal<Panel | null>(null);
  protected readonly errorCarga = signal(false);
  protected readonly mensaje = signal<{ error: boolean; texto: string } | null>(null);
  protected readonly errorDialogo = signal<string | null>(null);
  protected readonly ocupado = signal(false);
  /** Miniaturas de las fotos (blob: pedidas con el token, porque los álbumes sin publicar no son públicos). */
  protected readonly miniaturas = signal<Record<string, string>>({});

  // Ventanas
  protected readonly editandoTexto = signal<(typeof TEXTOS)[number] | null>(null);
  protected readonly editandoDatos = signal(false);
  protected readonly creandoAlbum = signal(false);
  protected readonly subiendoA = signal<AlbumClub | null>(null);
  protected readonly progreso = signal<string | null>(null);
  protected readonly creandoVideo = signal(false);
  protected readonly integrante = signal<IntegranteClub | 'nuevo' | null>(null);
  protected readonly confirmando = signal<{ titulo: string; texto: string; accion: () => void } | null>(null);

  protected readonly formTexto = this.fb.group({ texto: ['', Validators.maxLength(4000)] });
  protected readonly formDatos = this.fb.group({
    nombre: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(120)]],
    lema: ['', Validators.maxLength(160)],
    ciudad: ['', Validators.maxLength(80)],
    sede: ['', Validators.maxLength(160)],
    whatsapp: [''],
    correo: ['', Validators.email],
    instagram: [''],
    facebook: [''],
  });
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
  protected readonly formIntegrante = this.fb.group({
    nombre: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(120)]],
    cargo: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(120)]],
    bio: ['', Validators.maxLength(400)],
    orden: [''],
    publicado: true,
  });

  constructor() {
    inject(DestroyRef).onDestroy(() => Object.values(this.miniaturas()).forEach((u) => URL.revokeObjectURL(u)));
  }

  ngOnInit(): void {
    this.cargar();
  }

  private cargar(): void {
    this.http.get<Panel>(URL_CLUB).subscribe({
      next: (p) => {
        this.errorCarga.set(false);
        this.panel.set(p);
        this.cargarMiniaturas(p.albumes.flatMap((a) => a.fotos));
      },
      error: () => this.errorCarga.set(true),
    });
  }

  private cargarMiniaturas(fotos: FotoClub[]): void {
    for (const f of fotos) {
      if (this.miniaturas()[f.id]) continue;
      this.http.get(`${URL_CLUB}/fotos/${encodeURIComponent(f.id)}?tam=mini`, { responseType: 'blob' }).subscribe({
        next: (blob) => this.miniaturas.update((m) => ({ ...m, [f.id]: URL.createObjectURL(blob) })),
      });
    }
  }

  private ejecutar<T>(peticion: Observable<T>, ok: (r: T) => void, enDialogo = false): void {
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

  private abrir(accion: () => void): void {
    this.errorDialogo.set(null);
    this.mensaje.set(null);
    accion();
  }

  // ---------- Perfil ----------
  private guardarPerfil(cambios: Partial<PerfilClub>, texto: string, enDialogo: boolean, alTerminar?: () => void): void {
    this.ejecutar(this.http.patch<PerfilClub>(`${URL_CLUB}/perfil`, cambios), (perfil) => {
      this.panel.update((p) => (p ? { ...p, perfil } : p));
      alTerminar?.();
      this.exito(texto);
    }, enDialogo);
  }

  protected cambiarPublicado(): void {
    const p = this.panel()?.perfil;
    if (!p) return;
    this.guardarPerfil({ publicado: !p.publicado },
      p.publicado ? 'El sitio quedó oculto.' : 'El sitio quedó publicado.', false);
  }

  protected abrirTexto(t: (typeof TEXTOS)[number]): void {
    this.formTexto.reset({ texto: this.panel()?.perfil[t.campo] ?? '' });
    this.abrir(() => this.editandoTexto.set(t));
  }

  protected guardarTexto(): void {
    const t = this.editandoTexto();
    if (!t || this.formTexto.invalid) return;
    this.guardarPerfil({ [t.campo]: this.formTexto.getRawValue().texto.trim() || null },
      `${t.titulo} actualizada.`, true, () => this.editandoTexto.set(null));
  }

  protected abrirDatos(): void {
    const p = this.panel()?.perfil;
    if (!p) return;
    this.formDatos.reset({
      nombre: p.nombre, lema: p.lema ?? '', ciudad: p.ciudad ?? '', sede: p.sede ?? '', whatsapp: p.whatsapp ?? '',
      correo: p.correo ?? '', instagram: p.instagram ?? '', facebook: p.facebook ?? '',
    });
    this.abrir(() => this.editandoDatos.set(true));
  }

  protected guardarDatos(): void {
    if (this.formDatos.invalid) return this.errorDialogo.set('Revisa el nombre del club y el correo.');
    const f = this.formDatos.getRawValue();
    const vacio = (v: string) => v.trim() || null;
    this.guardarPerfil({
      nombre: f.nombre.trim(), lema: vacio(f.lema), ciudad: vacio(f.ciudad), sede: vacio(f.sede),
      whatsapp: vacio(f.whatsapp), correo: vacio(f.correo), instagram: vacio(f.instagram), facebook: vacio(f.facebook),
    }, 'Datos del club actualizados.', true, () => this.editandoDatos.set(false));
  }

  // ---------- Álbumes y fotos ----------
  protected abrirAlbum(): void {
    this.formAlbum.reset();
    this.abrir(() => this.creandoAlbum.set(true));
  }

  protected crearAlbum(): void {
    if (this.formAlbum.invalid) return this.errorDialogo.set('Escribe el nombre del álbum.');
    const f = this.formAlbum.getRawValue();
    this.ejecutar(this.http.post<AlbumClub>(`${URL_CLUB}/albumes`, { ...f, fecha: f.fecha || null }), (a) => {
      this.panel.update((p) => (p ? { ...p, albumes: [a, ...p.albumes] } : p));
      this.creandoAlbum.set(false);
      this.exito(`Álbum «${a.nombre}» creado. Ahora súbele fotos.`);
    }, true);
  }

  protected cambiarAlbum(a: AlbumClub): void {
    this.ejecutar(this.http.patch<AlbumClub>(`${URL_CLUB}/albumes/${encodeURIComponent(a.id)}`, { publicado: !a.publicado }),
      (nuevo) => {
        this.reemplazarAlbum(nuevo);
        this.exito(nuevo.publicado ? `«${nuevo.nombre}» ya se ve en el sitio.` : `«${nuevo.nombre}» quedó oculto.`);
      });
  }

  private reemplazarAlbum(a: AlbumClub): void {
    this.panel.update((p) => (p ? { ...p, albumes: p.albumes.map((x) => (x.id === a.id ? a : x)) } : p));
  }

  protected eliminarAlbum(a: AlbumClub): void {
    this.confirmar('Eliminar álbum', `Se borra «${a.nombre}» con sus ${a.fotos.length} fotos. No se puede deshacer.`, () =>
      this.ejecutar(this.http.delete(`${URL_CLUB}/albumes/${encodeURIComponent(a.id)}`), () => {
        this.panel.update((p) => (p ? { ...p, albumes: p.albumes.filter((x) => x.id !== a.id) } : p));
        this.confirmando.set(null);
        this.exito('Álbum eliminado.');
      }, true));
  }

  protected abrirFotos(a: AlbumClub): void {
    this.formFotos.reset();
    this.archivos = [];
    this.progreso.set(null);
    this.abrir(() => this.subiendoA.set(a));
  }

  protected elegirArchivos(e: Event): void {
    this.archivos = Array.from((e.target as HTMLInputElement).files ?? []);
  }

  /** Sube las fotos una por una (así una que falle no tumba las demás y se ve el avance). */
  protected subirFotos(): void {
    const a = this.subiendoA();
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
          this.subiendoA.set(null);
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
          this.panel.update((p) => (p ? {
            ...p, albumes: p.albumes.map((x) => (x.id === a.id ? { ...x, fotos: [...x.fotos, foto] } : x)),
          } : p));
          this.cargarMiniaturas([foto]);
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

  protected eliminarFoto(a: AlbumClub, f: FotoClub): void {
    this.confirmar('Eliminar foto', `La foto se borra de «${a.nombre}» y del sitio.`, () =>
      this.ejecutar(this.http.delete(`${URL_CLUB}/fotos/${encodeURIComponent(f.id)}`), () => {
        this.reemplazarAlbum({ ...a, fotos: a.fotos.filter((x) => x.id !== f.id) });
        const url = this.miniaturas()[f.id];
        if (url) URL.revokeObjectURL(url);
        this.confirmando.set(null);
        this.exito('Foto eliminada.');
      }, true));
  }

  // ---------- Videos ----------
  protected abrirVideo(): void {
    this.formVideo.reset();
    this.abrir(() => this.creandoVideo.set(true));
  }

  protected crearVideo(): void {
    if (this.formVideo.invalid) return this.errorDialogo.set('Escribe el título y pega el enlace de YouTube.');
    this.ejecutar(this.http.post<VideoClub>(`${URL_CLUB}/videos`, this.formVideo.getRawValue()), (v) => {
      this.panel.update((p) => (p ? { ...p, videos: [v, ...p.videos] } : p));
      this.creandoVideo.set(false);
      this.exito(`Video «${v.titulo}» agregado.`);
    }, true);
  }

  protected cambiarVideo(v: VideoClub): void {
    this.ejecutar(this.http.patch<VideoClub>(`${URL_CLUB}/videos/${encodeURIComponent(v.id)}`, { publicado: !v.publicado }),
      (nuevo) => {
        this.panel.update((p) => (p ? { ...p, videos: p.videos.map((x) => (x.id === v.id ? nuevo : x)) } : p));
        this.exito(nuevo.publicado ? 'Video publicado.' : 'Video oculto.');
      });
  }

  protected eliminarVideo(v: VideoClub): void {
    this.confirmar('Eliminar video', `Se quita «${v.titulo}» del sitio (en YouTube sigue igual).`, () =>
      this.ejecutar(this.http.delete(`${URL_CLUB}/videos/${encodeURIComponent(v.id)}`), () => {
        this.panel.update((p) => (p ? { ...p, videos: p.videos.filter((x) => x.id !== v.id) } : p));
        this.confirmando.set(null);
        this.exito('Video eliminado.');
      }, true));
  }

  // ---------- Equipo ----------
  protected abrirIntegrante(i: IntegranteClub | 'nuevo'): void {
    this.formIntegrante.reset(i === 'nuevo' ? undefined : {
      nombre: i.nombre, cargo: i.cargo, bio: i.bio ?? '', orden: String(i.orden), publicado: i.publicado,
    });
    this.abrir(() => this.integrante.set(i));
  }

  protected guardarIntegrante(): void {
    const actual = this.integrante();
    if (!actual) return;
    if (this.formIntegrante.invalid) return this.errorDialogo.set('Escribe el nombre y el cargo.');
    const f = this.formIntegrante.getRawValue();
    const orden = f.orden.trim() === '' ? 0 : Number(f.orden);
    if (!Number.isInteger(orden) || orden < 0 || orden > 999) return this.errorDialogo.set('El orden es un número de 0 a 999.');
    const cuerpo = { nombre: f.nombre.trim(), cargo: f.cargo.trim(), bio: f.bio.trim() || null, orden, publicado: f.publicado };
    const peticion = actual === 'nuevo'
      ? this.http.post<IntegranteClub>(`${URL_CLUB}/equipo`, cuerpo)
      : this.http.patch<IntegranteClub>(`${URL_CLUB}/equipo/${encodeURIComponent(actual.id)}`, cuerpo);
    this.ejecutar(peticion, (i) => {
      this.panel.update((p) => {
        if (!p) return p;
        const otros = p.equipo.filter((x) => x.id !== i.id);
        return { ...p, equipo: [...otros, i].sort((a, b) => a.orden - b.orden || a.nombre.localeCompare(b.nombre)) };
      });
      this.integrante.set(null);
      this.exito(actual === 'nuevo' ? `${i.nombre} agregado al equipo.` : `${i.nombre} actualizado.`);
    }, true);
  }

  protected eliminarIntegrante(i: IntegranteClub): void {
    this.confirmar('Quitar del equipo', `${i.nombre} deja de aparecer en el sitio.`, () =>
      this.ejecutar(this.http.delete(`${URL_CLUB}/equipo/${encodeURIComponent(i.id)}`), () => {
        this.panel.update((p) => (p ? { ...p, equipo: p.equipo.filter((x) => x.id !== i.id) } : p));
        this.confirmando.set(null);
        this.exito(`${i.nombre} quitado del equipo.`);
      }, true));
  }

  private confirmar(titulo: string, texto: string, accion: () => void): void {
    this.abrir(() => this.confirmando.set({ titulo, texto, accion }));
  }
}
