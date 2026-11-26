import { DOCUMENT } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';

import { PESTANAS_ALUMNOS, PESTANAS_CLUB, PESTANAS_RIFAS, Pestana } from '../compartido/pestanas';
import { AuthService } from './auth/auth.service';
import { AYUDAS } from './ayudas';
import { API } from './modelos';
import { PESTANAS_MOVIL, seccionesVisibles } from './secciones';

export type Pose = 'saluda' | 'senala' | 'remata';

/** Un paso del recorrido. `objetivo`: valor de `data-tutorial` que se resalta (null = burbuja al centro). */
export interface PasoTutorial {
  objetivo: string | null;
  pose: Pose;
  titulo: string;
  texto: string;
}

/** «panel» = el recorrido general; si no, la ruta de la pestaña («alumnos», «rifas/sorteo»; el Resumen es «resumen»). */
interface Recorrido {
  clave: string;
  pasos: PasoTutorial[];
}

/** Ancho máximo del celular: el mismo `$movil` de `layout/shell.scss` (ahí el menú lateral no se ve). */
const ANCHO_MOVIL = 899;

/** Qué hace cada sección del menú, en una frase: el recorrido general las presenta todas. */
export const QUE_HACE: Record<string, string> = {
  '': 'Lo importante de hoy: alertas que piden tu decisión, el entrenamiento del día y lo que falta por cobrar.',
  asistencia: 'Marca quién vino a entrenar. Quien no marca ni avisa recibe su multa al cierre del día.',
  alumnos: 'Fichas de los alumnos con acudientes, documentos e inscripción del año. Cada uno tiene su código, como F012.',
  asistente: 'Pregúntale en tus palabras, por ejemplo «¿quién debe multas?», y consulta los datos por ti.',
  rifas: 'Las rifas del año: un talonario por alumno, sus pagos y el sorteo con su acta.',
  reportes: 'Cuánto entró al club cada mes y por qué concepto. Desde aquí descargas los movimientos para la contabilidad.',
  multas: 'Las deudas por cobrar: multas, sus pagos y quién está cerca de entrar en mora.',
  torneos: 'Los torneos del club: clubes inscritos, cupos, pagos y el flyer que se ve en el sitio.',
  'perfil-club': 'Todo lo que se ve en el sitio público: textos, galería, entrenadores y torneos realizados.',
  avisos: 'Mensajes listos para enviar por WhatsApp con un clic, desde el número del club.',
  configuracion: 'Los valores del club: multa, plazos, valor de la inscripción y reglas de mora.',
  habeas: 'Consultas y reclamos sobre datos personales, con su plazo legal (Ley 1581).',
  usuarios: 'Las cuentas del staff: crearlas, asignar el rol, dar o quitar permisos y desactivarlas.',
};

/** Secciones con varias pestañas: al entrar a la primera, Kiira las señala. */
const GRUPOS_PESTANAS: Pestana[][] = [PESTANAS_ALUMNOS, PESTANAS_RIFAS, PESTANAS_CLUB];

const clave = (ruta: string) => ruta || 'resumen';

function enLista(nombres: string[]): string {
  return nombres.length < 2 ? nombres.join('') : `${nombres.slice(0, -1).join(', ')} y ${nombres.at(-1)}`;
}

/**
 * Kiira, el dragón del club, enseña el panel al staff (las familias tienen otro panel, más simple: no les sale).
 *
 * - **Recorrido general**: la primera vez que la cuenta entra. Presenta cada sección del menú; en el celular solo lo
 *   que se ve en pantalla (las pestañas de abajo y «Más»).
 * - **Recorrido de cada pestaña**: la primera vez que entra a cada una, explica cómo funciona (con el contenido de su
 *   ayuda). El botón «?» lo repite cuando quiera.
 *
 * Lo visto lo guarda el servidor por cuenta: no se repite en otro dispositivo (en el demo sale en cada ingreso).
 */
@Injectable({ providedIn: 'root' })
export class TutorialService {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private readonly doc = inject(DOCUMENT);

  readonly activo = signal(false);
  readonly indice = signal(0);
  private readonly recorrido = signal<Recorrido | null>(null);

  readonly pasos = computed(() => this.recorrido()?.pasos ?? []);
  readonly paso = computed(() => this.pasos()[this.indice()] ?? null);
  /** true = el recorrido de una pestaña (no el general). */
  readonly dePestana = computed(() => (this.recorrido()?.clave ?? 'panel') !== 'panel');

  private esStaff(): boolean {
    const u = this.auth.usuario();
    return !!u && u.rol !== 'MIEMBRO';
  }

  /** El recorrido general: al staff que nunca lo vio. */
  debeMostrarse(): boolean {
    return this.esStaff() && this.auth.usuario()?.tutorial_visto === false;
  }

  /** El de esta pestaña: después del general, si nunca la vio y tiene algo que explicarle. */
  pestanaPendiente(ruta: string): boolean {
    const u = this.auth.usuario();
    return this.esStaff() && !!u?.tutorial_visto && !u.tutoriales_vistos.includes(clave(ruta))
      && this.pasosDePestana(ruta).length > 0;
  }

  /** `ruta`: la pantalla abierta (el cierre avisa si su recorrido viene a continuación). */
  iniciarPanel(ruta: string | null = null): void {
    const u = this.auth.usuario();
    if (!u) return;
    const nombre = u.nombre.trim().split(/\s+/)[0] ?? '';
    const secciones = seccionesVisibles((p) => this.auth.tieneAlguno(p));
    const movil = typeof this.doc.defaultView?.matchMedia === 'function'
      && this.doc.defaultView.matchMedia(`(max-width: ${ANCHO_MOVIL}px)`).matches;
    const presentar = (s: (typeof secciones)[number]): PasoTutorial => ({
      objetivo: `seccion:${s.ruta}`, pose: 'senala', titulo: s.etiqueta, texto: QUE_HACE[s.ruta] ?? s.descripcion,
    });

    const pasos: PasoTutorial[] = [{
      objetivo: null, pose: 'saluda', titulo: `¡Hola, ${nombre}!`,
      texto: 'Soy Kiira, el dragón del club. Te muestro el menú del panel. Puedes saltarlo cuando quieras.',
    }];
    if (movil) {
      // En el celular el menú lateral no se ve: solo las pestañas de abajo y, en «Más», el resto.
      const abajo = secciones.filter((s) => PESTANAS_MOVIL.includes(s.ruta));
      const resto = secciones.filter((s) => !PESTANAS_MOVIL.includes(s.ruta));
      pasos.push(...abajo.map(presentar));
      if (resto.length) {
        pasos.push({
          objetivo: 'mas', pose: 'senala', titulo: 'Más',
          texto: `Aquí está el resto del menú: ${enLista(resto.map((s) => s.etiqueta))}. Cada una te la explico al entrar.`,
        });
      }
    } else {
      pasos.push(...secciones.map(presentar));
    }
    pasos.push({
      objetivo: 'ayuda', pose: 'senala', titulo: '¿Dudas?',
      texto: 'Este botón explica la pantalla en la que estás. Tócalo cuando quieras repetir su recorrido.',
    });
    const sigue = ruta !== null && this.pestanaPendienteTrasPanel(ruta);
    pasos.push({
      objetivo: null, pose: 'remata', titulo: '¡A jugar!',
      texto: 'La primera vez que entres a cada pestaña te explico cómo funciona.'
        + (sigue ? ' Empecemos por esta.' : ' Ya conoces la cancha. A rematar.'),
    });
    this.empezar({ clave: 'panel', pasos });
  }

  /** El recorrido de una pestaña. Devuelve false si no hay nada que explicar. */
  iniciarPestana(ruta: string): boolean {
    const ayuda = AYUDAS[ruta];
    const explicacion = this.pasosDePestana(ruta);
    if (!ayuda || !explicacion.length) return false;
    const pasos: PasoTutorial[] = [{
      objetivo: null, pose: 'saluda', titulo: ayuda.titulo,
      texto: ayuda.intro ?? 'Te explico esta pantalla en unos pasos. Puedes saltarlo; el botón «?» lo repite.',
    }];
    const grupo = GRUPOS_PESTANAS.find((g) => g.some((p) => p.ruta === `/${ruta}`));
    if (grupo?.[0]?.ruta === `/${ruta}`) {
      pasos.push({
        objetivo: 'pestanas', pose: 'senala', titulo: 'Pestañas',
        texto: `Esta sección tiene varias vistas: ${enLista(grupo.map((p) => p.texto))}. Cada una tiene su recorrido.`,
      });
    }
    pasos.push(...explicacion);
    if (ayuda.nota) pasos.push({ objetivo: null, pose: 'remata', titulo: 'Ten en cuenta', texto: ayuda.nota });
    else pasos.push({ ...(pasos.pop() as PasoTutorial), pose: 'remata' });
    this.empezar({ clave: clave(ruta), pasos });
    return true;
  }

  siguiente(): void {
    if (this.indice() < this.pasos().length - 1) this.indice.update((i) => i + 1);
    else this.terminar();
  }

  anterior(): void {
    this.indice.update((i) => Math.max(0, i - 1));
  }

  /** Al terminar o saltarlo: queda visto en el servidor para esta cuenta (verlo otra vez no lo vuelve a enviar). */
  terminar(): void {
    const r = this.recorrido();
    this.activo.set(false);
    const u = this.auth.usuario();
    if (!r || !u) return;
    if (r.clave === 'panel') {
      if (u.tutorial_visto) return;
      this.auth.usuario.set({ ...u, tutorial_visto: true });
      this.http.post(`${API}/auth/tutorial`, {}).subscribe({ error: () => undefined }); // si falla, sale otra vez
      return;
    }
    if (u.tutoriales_vistos.includes(r.clave)) return;
    this.auth.usuario.set({ ...u, tutoriales_vistos: [...u.tutoriales_vistos, r.clave] });
    this.http.post(`${API}/auth/tutorial`, { recorrido: r.clave }).subscribe({ error: () => undefined });
  }

  private empezar(r: Recorrido): void {
    this.recorrido.set(r);
    this.indice.set(0);
    this.activo.set(true);
  }

  /** Los pasos de la ayuda de esa pantalla que le corresponden a esta persona. */
  private pasosDePestana(ruta: string): PasoTutorial[] {
    return (AYUDAS[ruta]?.pasos ?? [])
      .filter((p) => !p.permisos || this.auth.tieneAlguno(p.permisos))
      .map((p) => ({ objetivo: null, pose: 'senala' as const, titulo: p.titulo, texto: p.texto }));
  }

  /** ¿Después del general vendrá el de esta pestaña? (El general aún no está marcado como visto.) */
  private pestanaPendienteTrasPanel(ruta: string): boolean {
    const u = this.auth.usuario();
    return this.esStaff() && !u?.tutoriales_vistos.includes(clave(ruta)) && this.pasosDePestana(ruta).length > 0;
  }
}
