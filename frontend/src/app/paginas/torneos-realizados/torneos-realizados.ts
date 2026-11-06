import { DatePipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { Aviso } from '../../compartido/aviso';
import { AlbumClub, TorneoRealizadoClub } from '../../compartido/club';
import { Dialogo } from '../../compartido/dialogo';
import { mensajeError } from '../../compartido/errores';
import { Operacion } from '../../compartido/operacion';
import { PESTANAS_CLUB, Pestanas } from '../../compartido/pestanas';
import { reducirImagen } from '../../compartido/reducir-imagen';
import { ZonaArchivos } from '../../compartido/zona-archivos';
import { API } from '../../core/modelos';

const URL_TORNEOS = `${API}/club/torneos-realizados`;

/** «Torneos realizados» del sitio: torneos ya jugados con su anuncio (afiche), resultados y fotos. */
@Component({
  selector: 'app-torneos-realizados',
  imports: [DatePipe, ReactiveFormsModule, Aviso, Dialogo, Pestanas, ZonaArchivos],
  templateUrl: './torneos-realizados.html',
  styleUrl: './torneos-realizados.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class TorneosRealizadosPage implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly fb = inject(FormBuilder).nonNullable;

  protected readonly pestanas = PESTANAS_CLUB;

  protected readonly torneos = signal<TorneoRealizadoClub[] | null>(null);
  /** Álbumes de la galería, para enlazar las fotos del torneo. */
  protected readonly albumes = signal<AlbumClub[]>([]);
  protected readonly errorCarga = signal(false);
  protected readonly op = new Operacion();
  protected readonly mensaje = this.op.mensaje;
  protected readonly errorDialogo = this.op.errorDialogo;
  protected readonly ocupado = this.op.ocupado;
  /** Anuncios (blob:, pedidos con el token: uno oculto no es público), por "id:versión". */
  protected readonly anuncios = signal<Record<string, string>>({});

  protected readonly editando = signal<TorneoRealizadoClub | 'nuevo' | null>(null);
  protected readonly eliminando = signal<TorneoRealizadoClub | null>(null);
  /** Anuncio elegido en la ventana (se sube al guardar) o pedido de quitarlo. */
  protected archivoAnuncio: File | null = null;
  protected readonly quitarAnuncio = signal(false);

  protected readonly form = this.fb.group({
    nombre: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(120)]],
    fecha: ['', Validators.required],
    lugar: ['', Validators.maxLength(120)],
    resumen: ['', Validators.maxLength(600)],
    album_id: [''],
    publicado: true,
  });

  constructor() {
    inject(DestroyRef).onDestroy(() => Object.values(this.anuncios()).forEach((u) => URL.revokeObjectURL(u)));
  }

  ngOnInit(): void {
    this.http.get<TorneoRealizadoClub[]>(URL_TORNEOS).subscribe({
      next: (lista) => {
        this.torneos.set(lista);
        this.cargarAnuncios(lista);
      },
      error: () => this.errorCarga.set(true),
    });
    this.http.get<AlbumClub[]>(`${API}/club/albumes`).subscribe({ next: (a) => this.albumes.set(a) });
  }

  private cargarAnuncios(lista: TorneoRealizadoClub[]): void {
    for (const t of lista) {
      const clave = `${t.id}:${t.anuncio}`;
      if (!t.anuncio || this.anuncios()[clave]) continue;
      this.http.get(`${URL_TORNEOS}/${encodeURIComponent(t.id)}/anuncio`, { responseType: 'blob' }).subscribe({
        next: (blob) => this.anuncios.update((r) => ({ ...r, [clave]: URL.createObjectURL(blob) })),
      });
    }
  }

  protected anuncio(t: TorneoRealizadoClub): string | null {
    return t.anuncio ? (this.anuncios()[`${t.id}:${t.anuncio}`] ?? null) : null;
  }

  protected nombreAlbum(t: TorneoRealizadoClub): string | null {
    return t.album_id ? (this.albumes().find((a) => a.id === t.album_id)?.nombre ?? null) : null;
  }

  private poner(t: TorneoRealizadoClub): void {
    this.torneos.update((l) => {
      const otros = (l ?? []).filter((x) => x.id !== t.id);
      return [...otros, t].sort((a, b) => b.fecha.localeCompare(a.fecha) || a.nombre.localeCompare(b.nombre));
    });
    this.cargarAnuncios([t]);
  }

  protected abrir(t: TorneoRealizadoClub | 'nuevo'): void {
    this.form.reset(t === 'nuevo' ? undefined : {
      nombre: t.nombre, fecha: t.fecha, lugar: t.lugar ?? '', resumen: t.resumen ?? '',
      album_id: t.album_id ?? '', publicado: t.publicado,
    });
    this.archivoAnuncio = null;
    this.quitarAnuncio.set(false);
    this.errorDialogo.set(null);
    this.mensaje.set(null);
    this.editando.set(t);
  }

  protected elegirAnuncio(archivos: File[]): void {
    this.archivoAnuncio = archivos[0] ?? null;
    if (this.archivoAnuncio) {
      this.quitarAnuncio.set(false);
      const original = this.archivoAnuncio;
      void reducirImagen(original).then((f) => { if (this.archivoAnuncio === original) this.archivoAnuncio = f; });
    }
  }

  protected guardar(): void {
    const actual = this.editando();
    if (!actual) return;
    if (this.form.invalid) return this.errorDialogo.set('Escribe el nombre del torneo y la fecha en que se jugó.');
    const f = this.form.getRawValue();
    const cuerpo = {
      nombre: f.nombre.trim(), fecha: f.fecha, lugar: f.lugar.trim() || null, resumen: f.resumen.trim() || null,
      album_id: f.album_id || null, publicado: f.publicado,
    };
    const peticion = actual === 'nuevo'
      ? this.http.post<TorneoRealizadoClub>(URL_TORNEOS, cuerpo)
      : this.http.patch<TorneoRealizadoClub>(`${URL_TORNEOS}/${encodeURIComponent(actual.id)}`, cuerpo);
    this.op.ejecutar(peticion, (t) => {
      const listo = (final: TorneoRealizadoClub) => {
        this.poner(final);
        this.editando.set(null);
        this.mensaje.set({ error: false, texto: actual === 'nuevo' ? `${final.nombre} agregado a los torneos realizados.` : `${final.nombre} actualizado.` });
      };
      const url = `${URL_TORNEOS}/${encodeURIComponent(t.id)}/anuncio`;
      if (this.archivoAnuncio) {
        const datos = new FormData();
        datos.append('archivo', this.archivoAnuncio);
        this.poner(t); // los datos ya quedaron guardados aunque el anuncio falle
        this.op.ejecutar(this.http.post<TorneoRealizadoClub>(url, datos), listo);
      } else if (this.quitarAnuncio() && t.anuncio) {
        this.op.ejecutar(this.http.delete<TorneoRealizadoClub>(url), listo);
      } else {
        listo(t);
      }
    });
  }

  protected cambiarPublicado(t: TorneoRealizadoClub): void {
    this.mensaje.set(null);
    this.http.patch<TorneoRealizadoClub>(`${URL_TORNEOS}/${encodeURIComponent(t.id)}`, { publicado: !t.publicado }).subscribe({
      next: (nuevo) => {
        this.poner(nuevo);
        this.mensaje.set({ error: false, texto: nuevo.publicado ? `${nuevo.nombre} ya se ve en el sitio.` : `${nuevo.nombre} quedó oculto.` });
      },
      error: (e) => this.mensaje.set({ error: true, texto: mensajeError(e) }),
    });
  }

  protected abrirEliminar(t: TorneoRealizadoClub): void {
    this.errorDialogo.set(null);
    this.mensaje.set(null);
    this.eliminando.set(t);
  }

  protected eliminar(): void {
    const t = this.eliminando();
    if (!t) return;
    this.op.ejecutar(this.http.delete(`${URL_TORNEOS}/${encodeURIComponent(t.id)}`), () => {
      this.torneos.update((l) => (l ?? []).filter((x) => x.id !== t.id));
      this.eliminando.set(null);
      this.mensaje.set({ error: false, texto: `${t.nombre} salió de los torneos realizados.` });
    });
  }
}
