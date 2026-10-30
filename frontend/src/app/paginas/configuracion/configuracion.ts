import { HttpClient } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule } from '@angular/forms';

import { Aviso } from '../../compartido/aviso';
import { Dialogo } from '../../compartido/dialogo';
import { mensajeError } from '../../compartido/errores';
import { PesosPipe } from '../../compartido/pesos.pipe';
import { AuthService } from '../../core/auth/auth.service';
import { API } from '../../core/modelos';

type Valor = number | string | boolean | number[];
type Tipo = 'pesos' | 'numero' | 'hora' | 'booleano' | 'lista';

interface Parametro {
  clave: string;
  valor: Valor;
  descripcion: string | null;
}

/** Cómo se presenta cada parámetro: título, unidad y tipo de campo. */
interface Definicion {
  clave: string;
  titulo: string;
  tipo: Tipo;
  unidad?: string; // "días", "meses"…
  ayuda?: string;
}

const GRUPOS: { titulo: string; icono: string; parametros: Definicion[] }[] = [
  {
    titulo: 'Inscripciones', icono: 'assignment', parametros: [
      { clave: 'valor_inscripcion', titulo: 'Valor de la inscripción', tipo: 'pesos' },
      { clave: 'plazo_pago_dias', titulo: 'Plazo para pagar', tipo: 'numero', unidad: 'días' },
      { clave: 'recordatorios_dias_antes', titulo: 'Recordatorios de pago', tipo: 'lista', unidad: 'días antes', ayuda: 'Separa los días con comas (ej.: 7, 1).' },
      { clave: 'edad_mayoria', titulo: 'Mayoría de edad', tipo: 'numero', unidad: 'años', ayuda: 'Desde esta edad el alumno no necesita acudiente.' },
    ],
  },
  {
    titulo: 'Asistencia y multas', icono: 'fact_check', parametros: [
      { clave: 'multa_inasistencia', titulo: 'Multa por inasistencia', tipo: 'pesos', ayuda: '0 = no se multa.' },
      { clave: 'hora_cierre_asistencia', titulo: 'Cierre diario', tipo: 'hora' },
      { clave: 'minutos_marcar_antes', titulo: 'La familia marca desde', tipo: 'numero', unidad: 'minutos antes' },
      { clave: 'dias_para_justificar', titulo: 'Plazo para justificar', tipo: 'numero', unidad: 'días' },
      { clave: 'inasistencias_consecutivas_aviso', titulo: 'Aviso por inasistencias seguidas', tipo: 'numero', unidad: 'faltas' },
      { clave: 'dias_programacion_anticipada', titulo: 'Programar entrenamientos con', tipo: 'numero', unidad: 'días de anticipación' },
    ],
  },
  {
    titulo: 'Mora', icono: 'gavel', parametros: [
      { clave: 'meses_mora_expulsion', titulo: 'Mora tras', tipo: 'numero', unidad: 'meses sin pagar' },
      { clave: 'dias_aviso_mora', titulo: 'Aviso antes de la mora', tipo: 'numero', unidad: 'días' },
      { clave: 'expulsion_automatica', titulo: 'Expulsión automática', tipo: 'booleano', ayuda: 'Si está apagada, el SuperAdmin confirma cada expulsión.' },
    ],
  },
  {
    titulo: 'Rifas y torneos', icono: 'confirmation_number', parametros: [
      { clave: 'rifas_por_anio', titulo: 'Rifas por año', tipo: 'numero', unidad: 'rifas' },
      { clave: 'puestos_por_talonario', titulo: 'Boletas por talonario', tipo: 'numero', unidad: 'boletas' },
      { clave: 'precio_puesto', titulo: 'Precio de cada boleta', tipo: 'pesos' },
      { clave: 'cupo_equipos_sugerido', titulo: 'Cupo sugerido por torneo', tipo: 'numero', unidad: 'equipos' },
    ],
  },
  {
    titulo: 'Documentos', icono: 'description', parametros: [
      { clave: 'documento_max_mb', titulo: 'Tamaño máximo por archivo', tipo: 'numero', unidad: 'MB' },
    ],
  },
];

@Component({
  selector: 'app-configuracion',
  imports: [ReactiveFormsModule, Aviso, Dialogo],
  templateUrl: './configuracion.html',
  styleUrl: './configuracion.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ConfiguracionPage implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private readonly fb = inject(FormBuilder).nonNullable;
  private readonly pesos = new PesosPipe();

  protected readonly puedeEditar = computed(() => this.auth.tiene('config.editar'));

  protected readonly valores = signal<Record<string, Valor> | null>(null);
  protected readonly errorCarga = signal(false);
  protected readonly mensaje = signal<{ error: boolean; texto: string } | null>(null);
  protected readonly errorDialogo = signal<string | null>(null);
  protected readonly ocupado = signal(false);
  protected readonly editando = signal<Definicion | null>(null);
  protected readonly probando = signal(false);

  /** Un solo campo de texto: se interpreta según el tipo del parámetro. */
  protected readonly formValor = this.fb.group({ valor: [''], activo: false });

  protected readonly grupos = computed(() => {
    const v = this.valores();
    if (!v) return [];
    return GRUPOS.map((g) => ({ ...g, parametros: g.parametros.filter((p) => p.clave in v) }))
      .filter((g) => g.parametros.length);
  });

  ngOnInit(): void {
    this.http.get<Parametro[]>(`${API}/configuracion`).subscribe({
      next: (lista) => this.valores.set(Object.fromEntries(lista.map((p) => [p.clave, p.valor]))),
      error: () => this.errorCarga.set(true),
    });
  }

  /** "$90.000", "30 días", "7 y 1 días antes", "Sí"… */
  protected mostrar(d: Definicion): string {
    const v = this.valores()?.[d.clave];
    if (v === undefined) return '—';
    switch (d.tipo) {
      case 'pesos':
        return this.pesos.transform(v as number);
      case 'booleano':
        return v ? 'Activada' : 'Apagada';
      case 'hora':
        return String(v);
      case 'lista': {
        const l = v as number[];
        return l.length ? `${l.join(' y ')} ${d.unidad ?? ''}`.trim() : 'Ninguno';
      }
      default:
        return `${v} ${d.unidad ?? ''}`.trim();
    }
  }

  protected abrirEditar(d: Definicion): void {
    const actual = this.valores()?.[d.clave];
    this.formValor.reset({ valor: '', activo: actual === true });
    this.errorDialogo.set(null);
    this.mensaje.set(null);
    this.editando.set(d);
  }

  /** Valor actual como guía en el placeholder (el campo empieza vacío). */
  protected guia(d: Definicion): string {
    const v = this.valores()?.[d.clave];
    if (d.tipo === 'lista') return `Actual: ${(v as number[] | undefined)?.join(', ') ?? ''}`;
    return `Actual: ${String(v ?? '')}`;
  }

  /** Interpreta lo escrito según el tipo del parámetro. */
  private leerValor(d: Definicion): { valor: Valor } | { error: string } {
    const f = this.formValor.getRawValue();
    if (d.tipo === 'booleano') return { valor: f.activo };
    const texto = f.valor.trim();
    if (!texto) return { error: 'Escribe el nuevo valor.' };
    if (d.tipo === 'hora') {
      return /^([01]\d|2[0-3]):[0-5]\d$/.test(texto) ? { valor: texto } : { error: 'Escribe la hora como HH:MM (ej.: 23:59).' };
    }
    if (d.tipo === 'lista') {
      const numeros = texto.split(/[,\s]+/).filter(Boolean).map(Number);
      return numeros.every((n) => Number.isInteger(n) && n >= 0 && n <= 365)
        ? { valor: [...new Set(numeros)].sort((a, b) => b - a) }
        : { error: 'Escribe números de días separados por comas (ej.: 7, 1).' };
    }
    const n = Number(texto.replace(/\./g, ''));
    return Number.isInteger(n) && n >= 0 ? { valor: n } : { error: 'Escribe un número entero (sin decimales).' };
  }

  protected guardar(): void {
    const d = this.editando();
    if (!d) return;
    const leido = this.leerValor(d);
    if ('error' in leido) return this.errorDialogo.set(leido.error);
    this.ocupado.set(true);
    this.http.patch<Parametro>(`${API}/configuracion/${encodeURIComponent(d.clave)}`, { valor: leido.valor }).subscribe({
      next: (p) => {
        this.ocupado.set(false);
        this.editando.set(null);
        this.valores.update((v) => ({ ...(v ?? {}), [p.clave]: p.valor }));
        this.mensaje.set({ error: false, texto: `${d.titulo}: ${this.mostrar(d)}. Aplica a lo que se cree desde ahora.` });
      },
      error: (e) => {
        this.ocupado.set(false);
        this.errorDialogo.set(mensajeError(e));
      },
    });
  }

  protected probarCorreo(): void {
    this.mensaje.set(null);
    this.probando.set(true);
    this.http.post<{ enviado: boolean; modo: string; detalle: string }>(`${API}/notificaciones/correo-prueba`, {}).subscribe({
      next: (r) => {
        this.probando.set(false);
        this.mensaje.set(r.enviado
          ? { error: false, texto: r.modo === 'smtp' ? `Correo de prueba enviado. ${r.detalle}` : `Modo de prueba (${r.modo}): el correo quedó en el registro del servidor, no salió.` }
          : { error: true, texto: `No se pudo enviar: ${r.detalle}` });
      },
      error: (e) => {
        this.probando.set(false);
        this.mensaje.set({ error: true, texto: mensajeError(e) });
      },
    });
  }
}
