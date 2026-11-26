import { DatePipe } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, input, output, signal } from '@angular/core';
import { forkJoin } from 'rxjs';

import { Aviso } from '../../compartido/aviso';
import { Dialogo } from '../../compartido/dialogo';
import { mensajeError } from '../../compartido/errores';
import { Operacion } from '../../compartido/operacion';
import { API } from '../../core/modelos';
import { ActaGrupos, Equipo, EquipoGrupo, RamaTorneo, SorteoGrupos, Torneo } from './torneos.modelos';

/** Grupos que se sugieren para `n` equipos: de a 4 más o menos, entre 2 y 8, y al menos dos equipos por grupo. */
export function gruposSugeridos(n: number): number {
  const maximo = Math.min(8, Math.floor(n / 2));
  return Math.max(2, Math.min(maximo, Math.ceil(n / 4)));
}

interface VistaRama {
  rama: RamaTorneo;
  sorteo: SorteoGrupos | null;
  conCupo: Equipo[];
  opciones: number[]; // cuántos grupos se pueden sortear
}

/** Sorteo de grupos de un torneo, rama por rama: sortear (borrador), ajustar, confirmar (acta) y sedes. */
@Component({
  selector: 'app-grupos-torneo',
  imports: [DatePipe, Aviso, Dialogo],
  templateUrl: './grupos-torneo.html',
  styleUrl: './grupos-torneo.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class GruposTorneo implements OnInit {
  private readonly http = inject(HttpClient);

  readonly torneo = input.required<Torneo>();
  readonly cerrar = output();

  protected readonly op = new Operacion();
  protected readonly sorteos = signal<SorteoGrupos[] | null>(null);
  protected readonly equipos = signal<Equipo[] | null>(null);
  /** Grupos elegidos por rama (si no, el sugerido). */
  protected readonly cantidades = signal<Partial<Record<RamaTorneo, number>>>({});
  /** Rama cuyo sorteo ya publicado se quiere repetir: se pide confirmación. */
  protected readonly porRepetir = signal<RamaTorneo | null>(null);

  private get url(): string {
    return `${API}/torneos/${encodeURIComponent(this.torneo().id)}`;
  }

  protected readonly ramas = computed<VistaRama[]>(() => {
    const t = this.torneo();
    const sorteos = this.sorteos() ?? [];
    const equipos = this.equipos() ?? [];
    return [...new Set(t.jornadas.map((j) => j.rama))].sort().map((rama) => {
      const conCupo = equipos.filter((e) => e.rama === rama && (e.estado === 'confirmado' || e.estado === 'pendiente_pago'));
      const maximo = Math.min(8, Math.floor(conCupo.length / 2));
      return {
        rama, conCupo, sorteo: sorteos.find((s) => s.rama === rama) ?? null,
        opciones: Array.from({ length: Math.max(0, maximo - 1) }, (_, i) => i + 2),
      };
    });
  });

  ngOnInit(): void {
    this.cargar();
  }

  private cargar(): void {
    forkJoin({
      sorteos: this.http.get<SorteoGrupos[]>(`${this.url}/grupos`),
      equipos: this.http.get<Equipo[]>(`${this.url}/equipos`),
    }).subscribe({
      next: ({ sorteos, equipos }) => {
        this.sorteos.set(sorteos);
        this.equipos.set(equipos);
      },
      error: (e) => this.op.errorDialogo.set(mensajeError(e)),
    });
  }

  protected cantidad(r: VistaRama): number {
    const elegida = this.cantidades()[r.rama];
    return elegida && r.opciones.includes(elegida) ? elegida : gruposSugeridos(r.conCupo.length);
  }

  protected elegirCantidad(rama: RamaTorneo, ev: Event): void {
    const n = Number((ev.target as HTMLSelectElement).value);
    this.cantidades.update((c) => ({ ...c, [rama]: n }));
  }

  protected tamanos(n: number, grupos: number): string {
    const base = Math.floor(n / grupos);
    const grandes = n % grupos;
    return grandes ? `${grandes} de ${base + 1} y ${grupos - grandes} de ${base}` : `${grupos} de ${base}`;
  }

  /** Clubes de un grupo del acta; con * los que debían la inscripción al confirmar. */
  protected clubesActa(g: ActaGrupos['grupos'][number]): string {
    return g.equipos.map((e) => e.club + (e.estado === 'pendiente_pago' ? '*' : '')).join(', ');
  }

  protected cabezas(r: VistaRama): number {
    return r.conCupo.filter((e) => e.cabeza_serie).length;
  }

  protected sortear(r: VistaRama): void {
    if (r.sorteo?.confirmado_en && this.porRepetir() !== r.rama) {
      this.porRepetir.set(r.rama);
      return;
    }
    this.porRepetir.set(null);
    const grupos = this.cantidad(r);
    this.op.ejecutar(
      this.http.post<SorteoGrupos>(`${this.url}/grupos/${r.rama}/sortear`, { grupos }),
      (s) => {
        this.ponerSorteo(s);
        this.op.exito(`Rama ${r.rama}: ${grupos} grupos sorteados (borrador). Revisa y confirma para publicarlos.`);
      },
    );
  }

  protected confirmar(rama: RamaTorneo): void {
    this.op.ejecutar(this.http.post<SorteoGrupos>(`${this.url}/grupos/${rama}/confirmar`, {}), (s) => {
      this.ponerSorteo(s);
      this.op.exito(`Grupos de la rama ${rama} confirmados: ya se ven en el sitio y quedó el acta n.º ${s.actas.length}.`);
    });
  }

  protected alElegirSede(grupoId: string, ev: Event): void {
    const sede = (ev.target as HTMLSelectElement).value || null;
    this.op.ejecutar(
      this.http.put<SorteoGrupos>(`${this.url}/grupos/${encodeURIComponent(grupoId)}/sede`, { sede }),
      (s) => this.ponerSorteo(s),
    );
  }

  protected alMover(e: EquipoGrupo, ev: Event): void {
    const grupo_id = (ev.target as HTMLSelectElement).value || null;
    this.op.ejecutar(
      this.http.put<Equipo>(`${this.url}/equipos/${encodeURIComponent(e.id)}/grupo`, { grupo_id }),
      (nuevo) => {
        this.cargar();
        this.op.exito(nuevo.grupo ? `${e.nombre_club} pasó al grupo ${nuevo.grupo}.` : `${e.nombre_club} quedó sin grupo.`);
      },
    );
  }

  protected alternarCabeza(e: EquipoGrupo): void {
    const cabeza_serie = !e.cabeza_serie;
    this.op.ejecutar(
      this.http.put<Equipo>(`${this.url}/equipos/${encodeURIComponent(e.id)}/cabeza-serie`, { cabeza_serie }),
      () => this.cargar(),
    );
  }

  private ponerSorteo(s: SorteoGrupos): void {
    this.sorteos.update((l) => [...(l ?? []).filter((x) => x.rama !== s.rama), s]);
  }
}
