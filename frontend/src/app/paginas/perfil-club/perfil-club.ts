import { HttpClient } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Observable } from 'rxjs';

import { Aviso } from '../../compartido/aviso';
import {
  ETAPAS_BASE, Etapa, INTRO_BASE, ORDEN_CANCHA, PerfilClub,
} from '../../compartido/club';
import { Dialogo } from '../../compartido/dialogo';
import { mensajeError } from '../../compartido/errores';
import { PESTANAS_CLUB, Pestanas } from '../../compartido/pestanas';
import { API } from '../../core/modelos';

interface Panel {
  sitio_url: string | null;
  perfil: PerfilClub;
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
  imports: [ReactiveFormsModule, Aviso, Dialogo, Pestanas],
  templateUrl: './perfil-club.html',
  styleUrl: './perfil-club.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class PerfilClubPage implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly fb = inject(FormBuilder).nonNullable;

  protected readonly textos = TEXTOS;
  protected readonly pestanas = PESTANAS_CLUB;
  protected readonly ordenCancha = ORDEN_CANCHA;
  /** Etapas que muestra el sitio: las del panel o, si no hay, las fijas. */
  protected readonly etapas = computed<Etapa[]>(() => this.panel()?.perfil.formacion ?? ETAPAS_BASE);
  protected readonly introFormacion = computed(() => this.panel()?.perfil.formacion_intro ?? INTRO_BASE);
  protected readonly formacionPropia = computed(() => !!this.panel()?.perfil.formacion);

  protected readonly panel = signal<Panel | null>(null);
  protected readonly errorCarga = signal(false);
  protected readonly mensaje = signal<{ error: boolean; texto: string } | null>(null);
  protected readonly errorDialogo = signal<string | null>(null);
  protected readonly ocupado = signal(false);

  // Ventanas
  protected readonly editandoTexto = signal<(typeof TEXTOS)[number] | null>(null);
  protected readonly editandoDatos = signal(false);
  protected readonly editandoFormacion = signal(false);

  protected readonly formTexto = this.fb.group({ texto: ['', Validators.maxLength(4000)] });
  protected readonly formDatos = this.fb.group({
    nombre: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(120)]],
    sede: ['', Validators.maxLength(160)],
    fundado_en: ['', Validators.pattern(/^(19|20)\d{2}$/)],
    whatsapp: [''],
    correo: ['', Validators.email],
    instagram: [''],
    facebook: [''],
  });
  protected readonly formFormacion = this.fb.group({
    intro: ['', Validators.maxLength(600)],
    etapas: this.fb.array(ETAPAS_BASE.map(() => this.fb.group({ titulo: [''], texto: [''] }))),
  });

  ngOnInit(): void {
    this.cargar();
  }

  private cargar(): void {
    this.http.get<Panel>(URL_CLUB).subscribe({
      next: (p) => {
        this.errorCarga.set(false);
        this.panel.set(p);
      },
      error: () => this.errorCarga.set(true),
    });
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
      nombre: p.nombre, sede: p.sede ?? '',
      fundado_en: p.fundado_en ? String(p.fundado_en) : '', whatsapp: p.whatsapp ?? '',
      correo: p.correo ?? '', instagram: p.instagram ?? '', facebook: p.facebook ?? '',
    });
    this.abrir(() => this.editandoDatos.set(true));
  }

  protected guardarDatos(): void {
    if (this.formDatos.invalid) return this.errorDialogo.set('Revisa el nombre del club, el año de fundación y el correo.');
    const f = this.formDatos.getRawValue();
    const vacio = (v: string) => v.trim() || null;
    this.guardarPerfil({
      nombre: f.nombre.trim(), sede: vacio(f.sede),
      fundado_en: f.fundado_en.trim() ? Number(f.fundado_en) : null,
      whatsapp: vacio(f.whatsapp), correo: vacio(f.correo), instagram: vacio(f.instagram), facebook: vacio(f.facebook),
    }, 'Datos del club actualizados.', true, () => this.editandoDatos.set(false));
  }

  // ---------- La formación (rotación) ----------
  protected zona(n: number): Etapa {
    return this.etapas()[n - 1] ?? { titulo: '', texto: '' };
  }

  protected abrirFormacion(): void {
    this.formFormacion.reset({ intro: this.introFormacion(), etapas: this.etapas().map((e) => ({ ...e })) });
    this.abrir(() => this.editandoFormacion.set(true));
  }

  protected guardarFormacion(): void {
    const f = this.formFormacion.getRawValue();
    const etapas = f.etapas.map((e) => ({ titulo: e.titulo.trim(), texto: e.texto.trim() }));
    const mala = etapas.findIndex((e) => e.titulo.length < 2 || e.titulo.length > 60 || e.texto.length < 2 || e.texto.length > 200);
    if (mala >= 0) return this.errorDialogo.set(`Zona ${mala + 1}: el título va de 2 a 60 letras y el texto de 2 a 200.`);
    this.guardarPerfil({ formacion_intro: f.intro.trim() || null, formacion: etapas },
      'La formación quedó actualizada en el sitio.', true, () => this.editandoFormacion.set(false));
  }

  protected restablecerFormacion(): void {
    this.guardarPerfil({ formacion_intro: null, formacion: null },
      'Se restablecieron las etapas originales del sitio.', true, () => this.editandoFormacion.set(false));
  }
}
