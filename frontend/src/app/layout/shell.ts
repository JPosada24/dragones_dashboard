import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter, map, startWith, tap } from 'rxjs';

import { Ayuda, AyudaBoton } from '../compartido/ayuda';
import { AuthService } from '../core/auth/auth.service';
import { NOMBRE_ROL } from '../core/modelos';
import { NotificacionesService } from '../core/notificaciones.service';
import { Campana } from './campana/campana';
import { GRUPOS, PESTANAS_MOVIL, Seccion, seccionesVisibles } from '../core/secciones';

@Component({
  selector: 'app-shell',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, Campana, AyudaBoton],
  templateUrl: './shell.html',
  styleUrl: './shell.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class Shell {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly ruta = inject(ActivatedRoute);
  protected readonly avisos = inject(NotificacionesService);

  protected readonly usuario = this.auth.usuario;
  protected readonly menuAbierto = signal(false);

  protected readonly secciones = computed(() => {
    this.usuario(); // se recalcula si cambia el usuario
    return seccionesVisibles((p) => this.auth.tieneAlguno(p));
  });

  protected readonly grupos = computed(() =>
    GRUPOS.map((titulo) => ({ titulo, secciones: this.secciones().filter((s) => s.grupo === titulo) })).filter(
      (g) => g.secciones.length > 0,
    ),
  );

  protected readonly pestanas = computed(() => this.secciones().filter((s) => PESTANAS_MOVIL.includes(s.ruta)));

  protected readonly rol = computed(() => {
    const u = this.usuario();
    if (!u) return '';
    return u.rama && u.rol === 'ENTRENADOR' ? `${NOMBRE_ROL[u.rol]} · ${u.rama}` : NOMBRE_ROL[u.rol];
  });

  protected readonly iniciales = computed(() =>
    (this.usuario()?.nombre ?? '')
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((p) => p.charAt(0).toUpperCase())
      .join(''),
  );

  /** Título y subtítulo de la pantalla actual (vienen de los datos de la ruta). */
  protected readonly encabezado = toSignal(
    this.router.events.pipe(
      filter((e) => e instanceof NavigationEnd),
      startWith(null),
      tap(() => {
        this.menuAbierto.set(false);
        this.avisos.actualizarConteo();
      }),
      map(() => {
        let r = this.ruta.snapshot;
        while (r.firstChild) r = r.firstChild;
        return {
          titulo: (r.data['titulo'] as string) ?? '',
          subtitulo: (r.data['subtitulo'] as string) ?? '',
          ayuda: (r.data['ayuda'] as Ayuda | undefined) ?? null,
        };
      }),
    ),
    { initialValue: { titulo: '', subtitulo: '', ayuda: null as Ayuda | null } },
  );

  protected enlace(s: Seccion): string {
    return `/${s.ruta}`;
  }

  protected alternarMenu(): void {
    this.menuAbierto.update((v) => !v);
  }

  protected salir(): void {
    void this.auth.logout();
  }
}
