import { HttpClient, HttpParams } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';

import { Operacion } from '../../compartido/operacion';
import { Aviso } from '../../compartido/aviso';
import { Dialogo } from '../../compartido/dialogo';
import { mensajeError } from '../../compartido/errores';
import { Esquema } from '../../core/api/tipos';
import { AuthService } from '../../core/auth/auth.service';
import { API, NOMBRE_ROL, Rol, Usuario } from '../../core/modelos';
import { Alumno } from '../alumnos/alumnos.modelos';

/** Una cuenta con la persona a la que pertenece (si es Miembro) y si tiene permisos personalizados. */
type UsuarioLista = Esquema<'UsuarioListaOut'>;
type RolesOut = Esquema<'RolesOut'>;
type PermisosUsuario = Esquema<'PermisosUsuarioOut'>;

type Vinculo = 'acudiente' | 'alumno';

const ROLES: { valor: Rol; texto: string; descripcion: string }[] = [
  { valor: 'SUPERADMIN', texto: 'SuperAdmin', descripcion: 'Acceso total (el dueño del club).' },
  { valor: 'ADMIN', texto: 'Admin', descripcion: 'Todo el club (alumnos, cobros, rifas, torneos, parámetros) menos las cuentas de usuario.' },
  { valor: 'ENTRENADOR', texto: 'Entrenador', descripcion: 'Ambas ramas: alumnos, asistencia e inscripciones; no cobra multas ni rifas.' },
  { valor: 'MIEMBRO', texto: 'Miembro', descripcion: 'Acudiente o alumno mayor de edad: solo consulta lo suyo.' },
];

/** Área de cada permiso (lo que va antes del punto) para agruparlos al ajustarlos. */
const AREAS: Record<string, string> = {
  alumnos: 'Alumnos', inscripciones: 'Inscripciones', prorroga: 'Inscripciones', expulsion: 'Inscripciones',
  sesiones: 'Asistencia', asistencia: 'Asistencia', justificaciones: 'Asistencia',
  pagos: 'Cobros', multas: 'Cobros', rifas: 'Rifas', sorteo: 'Rifas', eventos: 'Torneos',
  reportes: 'Reportes', notificaciones: 'Avisos', club: 'Sitio público', config: 'Configuración',
  auditoria: 'Configuración', habeas: 'Datos personales', agente: 'Asistente de IA',
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
  ['config.editar', 'Cambiar parámetros críticos'],
  ['usuarios.gestionar', 'Cuentas y permisos'],
];

const NOMBRE_CORTO: Record<string, string> = { SUPERADMIN: 'Super', ADMIN: 'Admin', ENTRENADOR: 'Entren.', MIEMBRO: 'Miembro' };

/** Política del servidor: 12+ caracteres, con mayúscula, minúscula y número. */
const POLITICA = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).{12,128}$/;

/** Contraseña aleatoria que cumple la política (generada en el navegador con un generador seguro). */
export function generarContrasena(largo = 16): string {
  const grupos = ['ABCDEFGHJKLMNPQRSTUVWXYZ', 'abcdefghijkmnopqrstuvwxyz', '23456789'];
  const todos = grupos.join('');
  const azar = (n: number) => {
    const v = new Uint32Array(1);
    crypto.getRandomValues(v);
    return (v[0] ?? 0) % n;
  };
  const elegir = (s: string) => s.charAt(azar(s.length));
  const letras = [...grupos.map(elegir), ...Array.from({ length: largo - grupos.length }, () => elegir(todos))];
  for (let i = letras.length - 1; i > 0; i--) {
    const j = azar(i + 1);
    [letras[i], letras[j]] = [letras[j] ?? '', letras[i] ?? ''];
  }
  return letras.join('');
}

@Component({
  selector: 'app-usuarios',
  imports: [ReactiveFormsModule, Aviso, Dialogo],
  templateUrl: './usuarios.html',
  styleUrl: './usuarios.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class UsuariosPage implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private readonly fb = inject(FormBuilder).nonNullable;

  protected readonly roles = ROLES;
  protected readonly nombreRol = NOMBRE_ROL;
  protected readonly yo = computed(() => this.auth.usuario()?.id ?? null);
  protected readonly puedeEliminar = computed(() => this.auth.tiene('usuarios.eliminar'));
  protected readonly nombreCorto = NOMBRE_CORTO;

  /** Cuentas o la matriz de roles y permisos. */
  protected readonly vista = signal<'cuentas' | 'roles'>('cuentas');
  protected readonly matriz = signal<RolesOut | null>(null);
  protected readonly todosLosPermisos = signal(false);

  // ---------- Permisos de una persona ----------
  protected readonly ajustando = signal<UsuarioLista | null>(null);
  protected readonly permisosPersona = signal<PermisosUsuario | null>(null);
  protected readonly marcados = signal<ReadonlySet<string>>(new Set());

  protected readonly usuarios = signal<UsuarioLista[] | null>(null);
  protected readonly buscar = signal('');
  protected readonly filtroRol = signal<Rol | ''>('');
  protected readonly errorCarga = signal(false);
  protected readonly op = new Operacion();
  protected readonly mensaje = this.op.mensaje;
  protected readonly errorDialogo = this.op.errorDialogo;
  protected readonly ocupado = this.op.ocupado;

  // ---------- Ventanas emergentes ----------
  protected readonly creando = signal(false);
  protected readonly editando = signal<UsuarioLista | null>(null);
  protected readonly cambiandoClave = signal<UsuarioLista | null>(null);
  protected readonly eliminando = signal<UsuarioLista | null>(null);
  /** Contraseña recién asignada: se muestra una vez para entregarla a la persona. */
  protected readonly claveEntregada = signal<{ email: string; clave: string } | null>(null);
  protected readonly candidatos = signal<Alumno[] | null>(null);
  protected readonly alumnoElegido = signal<Alumno | null>(null);
  private temporizador: ReturnType<typeof setTimeout> | undefined;

  protected readonly formNuevo = this.fb.group({
    nombre: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(120)]],
    email: ['', [Validators.required, Validators.email, Validators.maxLength(254)]],
    password: ['', [Validators.required, Validators.pattern(POLITICA)]],
    rol: this.fb.control<Rol | ''>('', Validators.required),
    vinculo: this.fb.control<Vinculo>('acudiente'),
    acudiente_id: [''],
  });
  protected readonly formEditar = this.fb.group({
    nombre: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(120)]],
    rol: this.fb.control<Rol | ''>('', Validators.required),
    activo: true,
  });
  protected readonly formClave = this.fb.group({ password: ['', [Validators.required, Validators.pattern(POLITICA)]] });

  protected readonly lista = computed(() => {
    const texto = this.buscar().trim().toLowerCase();
    const rol = this.filtroRol();
    return (this.usuarios() ?? []).filter((u) =>
      (!rol || u.rol === rol)
      && (!texto || u.nombre.toLowerCase().includes(texto) || u.email.includes(texto)),
    );
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

  /** Lo que se puede dar o quitar a una persona, agrupado por área. */
  protected readonly gruposPermisos = computed(() => {
    const m = this.matriz();
    if (!m) return [];
    const ajustables = new Set(m.personalizables);
    const grupos = new Map<string, { codigo: string; descripcion: string }[]>();
    for (const p of m.permisos) {
      if (!ajustables.has(p.codigo)) continue;
      const area = AREAS[p.codigo.split('.')[0] ?? ''] ?? 'Otros';
      grupos.set(area, [...(grupos.get(area) ?? []), p]);
    }
    return [...grupos].map(([titulo, permisos]) => ({ titulo, permisos }));
  });

  /** Cuántos permisos quedarían distintos a los de su rol. */
  protected readonly cambios = computed(() => {
    const p = this.permisosPersona();
    const m = this.matriz();
    if (!p || !m) return 0;
    const delRol = new Set(p.de_rol);
    return m.personalizables.filter((c) => delRol.has(c) !== this.marcados().has(c)).length;
  });

  protected readonly conteo = computed(() => {
    const c: Record<string, number> = {};
    for (const u of this.usuarios() ?? []) c[u.rol] = (c[u.rol] ?? 0) + 1;
    return c;
  });

  constructor() {
    inject(DestroyRef).onDestroy(() => clearTimeout(this.temporizador));
  }

  ngOnInit(): void {
    this.cargar();
    this.http.get<RolesOut>(`${API}/usuarios/roles`).subscribe({ next: (m) => this.matriz.set(m) });
  }

  protected cargar(): void {
    this.http.get<UsuarioLista[]>(`${API}/usuarios`).subscribe({
      next: (u) => {
        this.errorCarga.set(false);
        this.usuarios.set(u);
      },
      error: () => this.errorCarga.set(true),
    });
  }

  protected descripcionRol(rol: Rol | ''): string {
    return ROLES.find((r) => r.valor === rol)?.descripcion ?? '';
  }

  // ---------- Crear ----------
  protected abrirNuevo(): void {
    this.formNuevo.reset();
    this.candidatos.set(null);
    this.alumnoElegido.set(null);
    this.op.abrir(() => this.creando.set(true));
  }

  protected generar(control: 'nuevo' | 'clave'): void {
    const clave = generarContrasena();
    if (control === 'nuevo') this.formNuevo.controls.password.setValue(clave);
    else this.formClave.controls.password.setValue(clave);
  }

  /** Busca al alumno (o al hijo del acudiente) al que pertenece la cuenta del Miembro. */
  protected buscarAlumno(texto: string): void {
    clearTimeout(this.temporizador);
    this.alumnoElegido.set(null);
    this.formNuevo.controls.acudiente_id.setValue('');
    if (texto.trim().length < 2) return this.candidatos.set(null);
    this.temporizador = setTimeout(() => {
      const params = new HttpParams().set('buscar', texto.trim()).set('limit', 10);
      this.http.get<Alumno[]>(`${API}/alumnos`, { params }).subscribe({
        next: (r) => this.candidatos.set(r),
        error: (e) => this.errorDialogo.set(mensajeError(e)),
      });
    }, 300);
  }

  protected elegirAlumno(a: Alumno): void {
    this.alumnoElegido.set(a);
    const principal = a.acudientes.find((x) => x.principal) ?? a.acudientes[0];
    this.formNuevo.controls.acudiente_id.setValue(principal?.acudiente_id ?? '');
  }

  protected guardarNuevo(): void {
    const f = this.formNuevo.getRawValue();
    if (this.formNuevo.invalid) {
      return this.errorDialogo.set(this.formNuevo.controls.password.invalid && f.password
        ? 'La contraseña debe tener al menos 12 caracteres, con mayúscula, minúscula y número.'
        : 'Completa nombre, correo, contraseña y rol.');
    }
    const cuerpo: Record<string, unknown> = {
      nombre: f.nombre, email: f.email, password: f.password, rol: f.rol,
    };
    if (f.rol === 'MIEMBRO') {
      const a = this.alumnoElegido();
      if (!a) return this.errorDialogo.set('Busca el alumno al que pertenece esta cuenta.');
      if (f.vinculo === 'alumno') cuerpo['vincular_alumno_id'] = a.id;
      else if (f.acudiente_id) cuerpo['vincular_acudiente_id'] = f.acudiente_id;
      else return this.errorDialogo.set('Ese alumno no tiene acudientes: agrégalo en su ficha.');
    }
    this.op.ejecutar(this.http.post<Usuario>(`${API}/usuarios`, cuerpo), (u) => {
      this.creando.set(false);
      this.cargar();
      this.claveEntregada.set({ email: u.email, clave: f.password });
    });
  }

  // ---------- Editar ----------
  protected abrirEditar(u: UsuarioLista): void {
    this.formEditar.reset({ nombre: u.nombre, rol: u.rol, activo: u.activo });
    this.op.abrir(() => this.editando.set(u));
  }

  protected guardarEdicion(): void {
    const u = this.editando();
    if (!u) return;
    const f = this.formEditar.getRawValue();
    if (this.formEditar.invalid) return this.errorDialogo.set('Revisa el nombre y el rol.');
    const cuerpo: Record<string, unknown> = { nombre: f.nombre };
    if (u.id !== this.yo()) Object.assign(cuerpo, { rol: f.rol, activo: f.activo }); // nadie se quita su propio acceso
    this.op.ejecutar(this.http.patch<Usuario>(`${API}/usuarios/${encodeURIComponent(u.id)}`, cuerpo), () => {
      this.editando.set(null);
      this.cargar();
      this.op.exito(`Cuenta de ${f.nombre} actualizada.`);
    });
  }

  // ---------- Contraseña ----------
  protected abrirClave(u: UsuarioLista): void {
    this.formClave.reset();
    this.op.abrir(() => this.cambiandoClave.set(u));
  }

  protected guardarClave(): void {
    const u = this.cambiandoClave();
    if (!u) return;
    if (this.formClave.invalid) {
      return this.errorDialogo.set('La contraseña debe tener al menos 12 caracteres, con mayúscula, minúscula y número.');
    }
    const { password } = this.formClave.getRawValue();
    this.op.ejecutar(this.http.patch<Usuario>(`${API}/usuarios/${encodeURIComponent(u.id)}`, { password }), () => {
      this.cambiandoClave.set(null);
      this.claveEntregada.set({ email: u.email, clave: password });
    });
  }

  // ---------- Eliminar (solo SuperAdmin) ----------
  protected abrirEliminar(u: UsuarioLista): void {
    this.op.abrir(() => this.eliminando.set(u));
  }

  protected eliminar(): void {
    const u = this.eliminando();
    if (!u) return;
    this.op.ejecutar(this.http.delete(`${API}/usuarios/${encodeURIComponent(u.id)}`), () => {
      this.eliminando.set(null);
      this.usuarios.update((l) => l?.filter((x) => x.id !== u.id) ?? l);
      this.op.exito(`Se eliminó la cuenta de ${u.nombre}.`);
    });
  }

  // ---------- Permisos de una persona (Admin o Entrenador) ----------
  protected esAjustable(u: UsuarioLista): boolean {
    return (u.rol === 'ADMIN' || u.rol === 'ENTRENADOR') && u.id !== this.yo();
  }

  protected abrirPermisos(u: UsuarioLista): void {
    this.permisosPersona.set(null);
    this.op.abrir(() => this.ajustando.set(u));
    this.http.get<PermisosUsuario>(`${API}/usuarios/${encodeURIComponent(u.id)}/permisos`).subscribe({
      next: (p) => {
        this.permisosPersona.set(p);
        this.marcados.set(new Set(p.efectivos));
      },
      error: (e: unknown) => this.errorDialogo.set(mensajeError(e)),
    });
  }

  protected alternar(codigo: string): void {
    this.marcados.update((s) => {
      const nuevo = new Set(s);
      if (!nuevo.delete(codigo)) nuevo.add(codigo);
      return nuevo;
    });
  }

  /** 'agregado' si su rol no lo trae y está marcado; 'quitado' si lo trae y no está. */
  protected diferencia(codigo: string): 'agregado' | 'quitado' | null {
    const p = this.permisosPersona();
    if (!p) return null;
    const delRol = p.de_rol.includes(codigo);
    const marcado = this.marcados().has(codigo);
    if (marcado && !delRol) return 'agregado';
    if (!marcado && delRol) return 'quitado';
    return null;
  }

  protected volverAlRol(): void {
    const p = this.permisosPersona();
    if (p) this.marcados.set(new Set(p.de_rol));
  }

  protected guardarPermisos(): void {
    const u = this.ajustando();
    const m = this.matriz();
    if (!u || !m) return;
    const ajustables = new Set(m.personalizables);
    const permisos = [...this.marcados()].filter((c) => ajustables.has(c)).sort();
    this.op.ejecutar(
      this.http.put<PermisosUsuario>(`${API}/usuarios/${encodeURIComponent(u.id)}/permisos`, { permisos }),
      (p) => {
        this.ajustando.set(null);
        this.cargar();
        const n = p.concedidos.length + p.quitados.length;
        this.op.exito(n ? `Permisos de ${u.nombre} guardados (${n} distinto${n === 1 ? '' : 's'} a su rol).`
          : `${u.nombre} quedó con los permisos de su rol.`);
      },
    );
  }

  protected copiar(texto: string): void {
    void navigator.clipboard?.writeText(texto).then(() => this.op.exito('Copiado al portapapeles.'));
  }

}
