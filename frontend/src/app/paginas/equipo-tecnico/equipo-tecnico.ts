import { HttpClient } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Observable } from 'rxjs';

import { Aviso } from '../../compartido/aviso';
import { IntegranteClub, iniciales } from '../../compartido/club';
import { Dialogo } from '../../compartido/dialogo';
import { mensajeError } from '../../compartido/errores';
import { PESTANAS_CLUB, Pestanas } from '../../compartido/pestanas';
import { API } from '../../core/modelos';

const URL_EQUIPO = `${API}/club/equipo`;

/** «Nuestro equipo técnico» del sitio: entrenadores con cargo, presentación y foto. */
@Component({
  selector: 'app-equipo-tecnico',
  imports: [ReactiveFormsModule, Aviso, Dialogo, Pestanas],
  templateUrl: './equipo-tecnico.html',
  styleUrl: './equipo-tecnico.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class EquipoTecnicoPage implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly fb = inject(FormBuilder).nonNullable;

  protected readonly pestanas = PESTANAS_CLUB;
  protected readonly iniciales = iniciales;

  protected readonly equipo = signal<IntegranteClub[] | null>(null);
  protected readonly errorCarga = signal(false);
  protected readonly mensaje = signal<{ error: boolean; texto: string } | null>(null);
  protected readonly errorDialogo = signal<string | null>(null);
  protected readonly ocupado = signal(false);
  /** Fotos (blob:, pedidas con el token: un integrante oculto no es público), por "id:versión". */
  protected readonly retratos = signal<Record<string, string>>({});

  protected readonly editando = signal<IntegranteClub | 'nuevo' | null>(null);
  protected readonly eliminando = signal<IntegranteClub | null>(null);
  /** Foto elegida en la ventana (se sube al guardar) o pedido de quitarla. */
  protected archivoRetrato: File | null = null;
  protected readonly quitarRetrato = signal(false);

  protected readonly form = this.fb.group({
    nombre: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(120)]],
    cargo: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(120)]],
    bio: ['', Validators.maxLength(400)],
    orden: [''],
    publicado: true,
  });

  constructor() {
    inject(DestroyRef).onDestroy(() => Object.values(this.retratos()).forEach((u) => URL.revokeObjectURL(u)));
  }

  ngOnInit(): void {
    this.http.get<IntegranteClub[]>(URL_EQUIPO).subscribe({
      next: (lista) => {
        this.equipo.set(lista);
        this.cargarRetratos(lista);
      },
      error: () => this.errorCarga.set(true),
    });
  }

  private cargarRetratos(lista: IntegranteClub[]): void {
    for (const i of lista) {
      const clave = `${i.id}:${i.foto}`;
      if (!i.foto || this.retratos()[clave]) continue;
      this.http.get(`${URL_EQUIPO}/${encodeURIComponent(i.id)}/foto`, { responseType: 'blob' }).subscribe({
        next: (blob) => this.retratos.update((r) => ({ ...r, [clave]: URL.createObjectURL(blob) })),
      });
    }
  }

  protected retrato(i: IntegranteClub): string | null {
    return i.foto ? (this.retratos()[`${i.id}:${i.foto}`] ?? null) : null;
  }

  private poner(i: IntegranteClub): void {
    this.equipo.update((l) => {
      const otros = (l ?? []).filter((x) => x.id !== i.id);
      return [...otros, i].sort((a, b) => a.orden - b.orden || a.nombre.localeCompare(b.nombre));
    });
    this.cargarRetratos([i]);
  }

  private ejecutar<T>(peticion: Observable<T>, ok: (r: T) => void): void {
    this.ocupado.set(true);
    this.errorDialogo.set(null);
    peticion.subscribe({
      next: (r) => {
        this.ocupado.set(false);
        ok(r);
      },
      error: (e) => {
        this.ocupado.set(false);
        this.errorDialogo.set(mensajeError(e));
      },
    });
  }

  protected abrir(i: IntegranteClub | 'nuevo'): void {
    this.form.reset(i === 'nuevo' ? undefined : {
      nombre: i.nombre, cargo: i.cargo, bio: i.bio ?? '', orden: String(i.orden), publicado: i.publicado,
    });
    this.archivoRetrato = null;
    this.quitarRetrato.set(false);
    this.errorDialogo.set(null);
    this.mensaje.set(null);
    this.editando.set(i);
  }

  protected elegirRetrato(e: Event): void {
    this.archivoRetrato = (e.target as HTMLInputElement).files?.[0] ?? null;
    if (this.archivoRetrato) this.quitarRetrato.set(false);
  }

  protected guardar(): void {
    const actual = this.editando();
    if (!actual) return;
    if (this.form.invalid) return this.errorDialogo.set('Escribe el nombre y el cargo.');
    const f = this.form.getRawValue();
    const orden = f.orden.trim() === '' ? 0 : Number(f.orden);
    if (!Number.isInteger(orden) || orden < 0 || orden > 999) return this.errorDialogo.set('El orden es un número de 0 a 999.');
    const cuerpo = { nombre: f.nombre.trim(), cargo: f.cargo.trim(), bio: f.bio.trim() || null, orden, publicado: f.publicado };
    const peticion = actual === 'nuevo'
      ? this.http.post<IntegranteClub>(URL_EQUIPO, cuerpo)
      : this.http.patch<IntegranteClub>(`${URL_EQUIPO}/${encodeURIComponent(actual.id)}`, cuerpo);
    this.ejecutar(peticion, (i) => {
      const listo = (final: IntegranteClub) => {
        this.poner(final);
        this.editando.set(null);
        this.mensaje.set({ error: false, texto: actual === 'nuevo' ? `${final.nombre} agregado al equipo técnico.` : `${final.nombre} actualizado.` });
      };
      const url = `${URL_EQUIPO}/${encodeURIComponent(i.id)}/foto`;
      if (this.archivoRetrato) {
        const datos = new FormData();
        datos.append('archivo', this.archivoRetrato);
        this.poner(i); // los datos ya quedaron guardados aunque la foto falle
        this.ejecutar(this.http.post<IntegranteClub>(url, datos), listo);
      } else if (this.quitarRetrato() && i.foto) {
        this.ejecutar(this.http.delete<IntegranteClub>(url), listo);
      } else {
        listo(i);
      }
    });
  }

  protected cambiarPublicado(i: IntegranteClub): void {
    this.mensaje.set(null);
    this.http.patch<IntegranteClub>(`${URL_EQUIPO}/${encodeURIComponent(i.id)}`, { publicado: !i.publicado }).subscribe({
      next: (nuevo) => {
        this.poner(nuevo);
        this.mensaje.set({ error: false, texto: nuevo.publicado ? `${nuevo.nombre} ya se ve en el sitio.` : `${nuevo.nombre} quedó oculto.` });
      },
      error: (e) => this.mensaje.set({ error: true, texto: mensajeError(e) }),
    });
  }

  protected abrirEliminar(i: IntegranteClub): void {
    this.errorDialogo.set(null);
    this.mensaje.set(null);
    this.eliminando.set(i);
  }

  protected eliminar(): void {
    const i = this.eliminando();
    if (!i) return;
    this.ejecutar(this.http.delete(`${URL_EQUIPO}/${encodeURIComponent(i.id)}`), () => {
      this.equipo.update((l) => (l ?? []).filter((x) => x.id !== i.id));
      this.eliminando.set(null);
      this.mensaje.set({ error: false, texto: `${i.nombre} salió del equipo técnico.` });
    });
  }
}
