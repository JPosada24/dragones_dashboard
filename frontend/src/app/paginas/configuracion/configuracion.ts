import { NgTemplateOutlet } from '@angular/common';
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

/** Cómo se presenta cada parámetro: título, nota, unidad y tipo de campo. */
interface Definicion {
  clave: string;
  titulo: string;
  nota: string;
  tipo: Tipo;
  unidad?: string; // "días", "meses"…
}

interface Grupo {
  titulo: string;
  nota?: string;
  parametros: Definicion[];
}

interface RolesOut {
  permisos: { codigo: string; descripcion: string }[];
  roles: { codigo: string; nombre: string; descripcion: string | null; permisos: string[] }[];
}

const MULTAS: Grupo = {
  titulo: 'Multas y plazos', nota: 'Aplica a lo que se cree desde el cambio; lo ya creado conserva su valor', parametros: [
    { clave: 'multa_inasistencia', titulo: 'Valor de la multa por inasistencia', nota: 'Se cobra al cierre del día si no marcó ni justificó (0 = no se multa)', tipo: 'pesos', unidad: 'COP' },
    { clave: 'hora_cierre_asistencia', titulo: 'Hora de cierre de asistencia', nota: 'A esta hora se cierra el día y se generan las multas', tipo: 'hora' },
    { clave: 'valor_inscripcion', titulo: 'Valor de la inscripción', nota: 'Se aceptan abonos parciales', tipo: 'pesos', unidad: 'COP' },
    { clave: 'plazo_pago_dias', titulo: 'Plazo de pago de inscripción', nota: 'Días desde la inscripción', tipo: 'numero', unidad: 'días' },
    { clave: 'dias_para_justificar', titulo: 'Plazo para justificar', nota: 'Días después del entrenamiento', tipo: 'numero', unidad: 'días' },
    { clave: 'minutos_marcar_antes', titulo: 'La familia marca asistencia desde', nota: 'Minutos antes del inicio del entrenamiento', tipo: 'numero', unidad: 'min' },
  ],
};

const MORA: Grupo = {
  titulo: 'Mora y expulsión', parametros: [
    { clave: 'meses_mora_expulsion', titulo: 'Mora tras', nota: 'Meses con una deuda sin pagar (multas o rifas)', tipo: 'numero', unidad: 'meses' },
    { clave: 'dias_aviso_mora', titulo: 'Aviso antes de la mora', nota: 'Días antes en que se avisa a la familia', tipo: 'numero', unidad: 'días' },
    { clave: 'inasistencias_consecutivas_aviso', titulo: 'Alerta por inasistencias seguidas', nota: 'Avisa al staff al llegar a esta racha', tipo: 'numero', unidad: 'faltas' },
  ],
};

const RIFAS: Grupo = {
  titulo: 'Rifas y torneos', nota: 'Base para el paz y salvo y para las rifas nuevas', parametros: [
    { clave: 'rifas_por_anio', titulo: 'Rifas por año', nota: 'Máximo de rifas activas en un año', tipo: 'numero', unidad: 'rifas' },
    { clave: 'puestos_por_talonario', titulo: 'Boletas por talonario', nota: 'Un talonario por alumno en cada rifa', tipo: 'numero', unidad: 'boletas' },
    { clave: 'precio_puesto', titulo: 'Precio de cada boleta', nota: 'El talonario vale boletas × precio', tipo: 'pesos', unidad: 'COP' },
    { clave: 'cupo_equipos_sugerido', titulo: 'Cupo sugerido por torneo', nota: 'Se propone al crear un torneo', tipo: 'numero', unidad: 'equipos' },
  ],
};

const OTROS: Grupo = {
  titulo: 'Otros parámetros', parametros: [
    { clave: 'edad_mayoria', titulo: 'Mayoría de edad', nota: 'Desde esta edad no necesita acudiente', tipo: 'numero', unidad: 'años' },
    { clave: 'documento_max_mb', titulo: 'Tamaño máximo por documento', nota: 'PDF, JPG o PNG', tipo: 'numero', unidad: 'MB' },
    { clave: 'dias_programacion_anticipada', titulo: 'Programar entrenamientos con', nota: 'Días hacia adelante desde el horario semanal', tipo: 'numero', unidad: 'días' },
    { clave: 'agente_mensajes_por_dia', titulo: 'Preguntas al asistente de IA', nota: 'Por usuario y por día; 0 = asistente apagado', tipo: 'numero', unidad: 'al día' },
  ],
};

const RECORDATORIOS: Definicion = {
  clave: 'recordatorios_dias_antes', titulo: 'Recordatorios de pago', nota: 'Separa los días con comas (ej.: 7, 1).', tipo: 'lista', unidad: 'días antes',
};

const EXPULSION: Definicion = {
  clave: 'expulsion_automatica', titulo: 'Expulsión automática por mora', nota: '', tipo: 'booleano',
};

/** Permisos que se muestran en la matriz resumida (el resto con "Ver todos"). */
const PERMISOS_CLAVE: [string, string][] = [
  ['asistencia.marcar_grupo', 'Marcar asistencia'],
  ['inscripciones.crear', 'Inscribir alumnos'],
  ['inscripciones.abonar', 'Abonos de inscripción'],
  ['pagos.registrar', 'Cobrar multas y rifas'],
  ['pagos.anular', 'Anular pagos'],
  ['prorroga.conceder', 'Conceder prórrogas'],
  ['rifas.gestionar', 'Crear y gestionar rifas'],
  ['eventos.gestionar', 'Crear y gestionar torneos'],
  ['alumnos.eliminar', 'Eliminar alumnos'],
  ['usuarios.gestionar', 'Crear usuarios'],
  ['config.editar', 'Cambiar parámetros críticos'],
];

const NOMBRE_CORTO: Record<string, string> = { SUPERADMIN: 'Super', ADMIN: 'Admin', ENTRENADOR: 'Entren.', MIEMBRO: 'Miembro' };

@Component({
  selector: 'app-configuracion',
  imports: [NgTemplateOutlet, ReactiveFormsModule, Aviso, Dialogo],
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
  protected readonly recordatoriosDef = RECORDATORIOS;
  protected readonly nombreCorto = NOMBRE_CORTO;

  protected readonly valores = signal<Record<string, Valor> | null>(null);
  protected readonly matriz = signal<RolesOut | null>(null);
  protected readonly todosLosPermisos = signal(false);
  protected readonly errorCarga = signal(false);
  protected readonly mensaje = signal<{ error: boolean; texto: string } | null>(null);
  protected readonly errorDialogo = signal<string | null>(null);
  protected readonly ocupado = signal(false);
  protected readonly cambiandoPolitica = signal(false);
  protected readonly editando = signal<Definicion | null>(null);
  protected readonly probando = signal(false);

  /** Un solo campo de texto: se interpreta según el tipo del parámetro. */
  protected readonly formValor = this.fb.group({ valor: [''] });

  private filtrar(g: Grupo): Grupo {
    const v = this.valores() ?? {};
    return { ...g, parametros: g.parametros.filter((p) => p.clave in v) };
  }

  protected readonly izquierda = computed(() => (this.valores() ? [MULTAS, RIFAS].map((g) => this.filtrar(g)) : []));
  protected readonly mora = computed(() => this.filtrar(MORA));
  protected readonly otros = computed(() => this.filtrar(OTROS));

  protected readonly expulsionAutomatica = computed(() => this.valores()?.['expulsion_automatica'] === true);

  /** Filas de la tarjeta "Recordatorios": los días configurados, el vencimiento y el aviso de mora. */
  protected readonly recordatorios = computed(() => {
    const v = this.valores();
    if (!v) return [];
    const dias = (v['recordatorios_dias_antes'] as number[] | undefined) ?? [];
    const filas: { cuando: string; canal: string; nota: string; tono: 'oro' | 'rojo' }[] = dias.map((d) => ({
      cuando: d === 0 ? 'EL DÍA' : `${d} ${d === 1 ? 'DÍA' : 'DÍAS'}`,
      canal: 'Correo + WhatsApp a la familia',
      nota: d === 0 ? 'El día que vence la inscripción' : 'Antes de que venza el plazo de la inscripción',
      tono: d <= 1 ? 'rojo' : 'oro',
    }));
    filas.push({ cuando: 'VENCIDO', canal: 'Correo + WhatsApp a la familia', nota: 'Inscripción rechazada por falta de pago', tono: 'rojo' });
    if (typeof v['dias_aviso_mora'] === 'number') {
      filas.push({ cuando: `${v['dias_aviso_mora']} DÍAS`, canal: 'Correo + WhatsApp a la familia', nota: 'Antes de entrar en mora por deudas', tono: 'oro' });
    }
    return filas;
  });

  /** Matriz de permisos: resumida o completa. */
  protected readonly filasPermisos = computed(() => {
    const m = this.matriz();
    if (!m) return [];
    const lista: [string, string][] = this.todosLosPermisos()
      ? m.permisos.map((p) => [p.codigo, p.descripcion])
      : PERMISOS_CLAVE.filter(([c]) => m.permisos.some((p) => p.codigo === c));
    return lista.map(([codigo, etiqueta]) => ({
      codigo, etiqueta, celdas: m.roles.map((r) => ({ rol: r.nombre, si: r.permisos.includes(codigo) })),
    }));
  });

  ngOnInit(): void {
    this.http.get<Parametro[]>(`${API}/configuracion`).subscribe({
      next: (lista) => this.valores.set(Object.fromEntries(lista.map((p) => [p.clave, p.valor]))),
      error: () => this.errorCarga.set(true),
    });
    this.http.get<RolesOut>(`${API}/configuracion/roles`).subscribe({
      next: (m) => this.matriz.set(m),
      error: () => this.matriz.set(null),
    });
  }

  /** Solo el valor: "$90.000", "30", "23:59", "7, 1"… (la unidad va aparte). */
  protected valor(d: Definicion): string {
    const v = this.valores()?.[d.clave];
    if (v === undefined) return '—';
    switch (d.tipo) {
      case 'pesos':
        return this.pesos.transform(v as number);
      case 'booleano':
        return v ? 'Activada' : 'Apagada';
      case 'lista': {
        const l = v as number[];
        return l.length ? l.join(', ') : 'Ninguno';
      }
      default:
        return String(v);
    }
  }

  /** Unidad junto al valor; la hora se muestra en formato de 12 h como ayuda. */
  protected unidad(d: Definicion): string {
    if (d.tipo === 'pesos') return 'COP';
    if (d.tipo === 'hora') {
      const v = this.valores()?.[d.clave];
      if (typeof v !== 'string') return '';
      const [h = 0, m = 0] = v.split(':').map(Number);
      return `${h % 12 || 12}:${String(m).padStart(2, '0')} ${h < 12 ? 'am' : 'pm'}`;
    }
    return d.unidad ?? '';
  }

  protected abrirEditar(d: Definicion): void {
    this.formValor.reset({ valor: '' });
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
    const texto = this.formValor.getRawValue().valor.trim();
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

  private enviar(d: Definicion, valor: Valor, alTerminar: (error: string | null) => void): void {
    this.http.patch<Parametro>(`${API}/configuracion/${encodeURIComponent(d.clave)}`, { valor }).subscribe({
      next: (p) => {
        this.valores.update((v) => ({ ...(v ?? {}), [p.clave]: p.valor }));
        alTerminar(null);
      },
      error: (e) => alTerminar(mensajeError(e)),
    });
  }

  protected guardar(): void {
    const d = this.editando();
    if (!d) return;
    const leido = this.leerValor(d);
    if ('error' in leido) return this.errorDialogo.set(leido.error);
    this.ocupado.set(true);
    this.enviar(d, leido.valor, (error) => {
      this.ocupado.set(false);
      if (error) return this.errorDialogo.set(error);
      this.editando.set(null);
      this.mensaje.set({ error: false, texto: `${d.titulo}: ${this.valor(d)} ${this.unidad(d)}`.trim() + '. Aplica desde ahora.' });
    });
  }

  protected cambiarExpulsion(): void {
    if (!this.puedeEditar() || this.cambiandoPolitica()) return;
    const nuevo = !this.expulsionAutomatica();
    this.cambiandoPolitica.set(true);
    this.mensaje.set(null);
    this.enviar(EXPULSION, nuevo, (error) => {
      this.cambiandoPolitica.set(false);
      this.mensaje.set(error
        ? { error: true, texto: error }
        : { error: false, texto: nuevo ? 'Expulsión automática activada: la mora expulsa sin confirmación.' : 'Expulsión automática apagada: el SuperAdmin confirma cada expulsión.' });
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
