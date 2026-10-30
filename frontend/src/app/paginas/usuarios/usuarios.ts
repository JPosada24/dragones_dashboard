import { HttpClient, HttpParams } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Observable } from 'rxjs';

import { Aviso } from '../../compartido/aviso';
import { Dialogo } from '../../compartido/dialogo';
import { mensajeError } from '../../compartido/errores';
import { AuthService } from '../../core/auth/auth.service';
import { API, NOMBRE_ROL, Rol, Usuario } from '../../core/modelos';
import { Alumno } from '../alumnos/alumnos.modelos';

/** Una cuenta con la persona a la que pertenece (si es Miembro). */
interface UsuarioLista extends Usuario {
  vinculado_a: string | null;
}

type Vinculo = 'acudiente' | 'alumno';

const ROLES: { valor: Rol; texto: string; descripcion: string }[] = [
  { valor: 'SUPERADMIN', texto: 'SuperAdmin', descripcion: 'Acceso total (el dueño del club).' },
  { valor: 'ADMIN', texto: 'Admin', descripcion: 'Alumnos, cobros, inscripciones, rifas y torneos.' },
  { valor: 'ENTRENADOR', texto: 'Entrenador', descripcion: 'Asistente de una rama: solo ve y gestiona su rama; no cobra.' },
  { valor: 'MIEMBRO', texto: 'Miembro', descripcion: 'Acudiente o alumno mayor de edad: solo consulta lo suyo.' },
];

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

  protected readonly usuarios = signal<UsuarioLista[] | null>(null);
  protected readonly buscar = signal('');
  protected readonly filtroRol = signal<Rol | ''>('');
  protected readonly errorCarga = signal(false);
  protected readonly mensaje = signal<{ error: boolean; texto: string } | null>(null);
  protected readonly errorDialogo = signal<string | null>(null);
  protected readonly ocupado = signal(false);

  // ---------- Ventanas emergentes ----------
  protected readonly creando = signal(false);
  protected readonly editando = signal<UsuarioLista | null>(null);
  protected readonly cambiandoClave = signal<UsuarioLista | null>(null);
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
    rama: this.fb.control<'' | 'femenina' | 'masculina'>(''),
    vinculo: this.fb.control<Vinculo>('acudiente'),
    acudiente_id: [''],
  });
  protected readonly formEditar = this.fb.group({
    nombre: ['', [Validators.required, Validators.minLength(2), Validators.maxLength(120)]],
    rol: this.fb.control<Rol | ''>('', Validators.required),
    rama: this.fb.control<'' | 'femenina' | 'masculina'>(''),
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
    this.abrir(() => this.creando.set(true));
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
    if (f.rol === 'ENTRENADOR' && !f.rama) return this.errorDialogo.set('Elige la rama del entrenador.');
    const cuerpo: Record<string, unknown> = {
      nombre: f.nombre, email: f.email, password: f.password, rol: f.rol, rama: f.rol === 'ENTRENADOR' ? f.rama : null,
    };
    if (f.rol === 'MIEMBRO') {
      const a = this.alumnoElegido();
      if (!a) return this.errorDialogo.set('Busca el alumno al que pertenece esta cuenta.');
      if (f.vinculo === 'alumno') cuerpo['vincular_alumno_id'] = a.id;
      else if (f.acudiente_id) cuerpo['vincular_acudiente_id'] = f.acudiente_id;
      else return this.errorDialogo.set('Ese alumno no tiene acudientes: agrégalo en su ficha.');
    }
    this.ejecutar(this.http.post<Usuario>(`${API}/usuarios`, cuerpo), (u) => {
      this.creando.set(false);
      this.cargar();
      this.claveEntregada.set({ email: u.email, clave: f.password });
    });
  }

  // ---------- Editar ----------
  protected abrirEditar(u: UsuarioLista): void {
    this.formEditar.reset({ nombre: u.nombre, rol: u.rol, rama: u.rama ?? '', activo: u.activo });
    this.abrir(() => this.editando.set(u));
  }

  protected guardarEdicion(): void {
    const u = this.editando();
    if (!u) return;
    const f = this.formEditar.getRawValue();
    if (this.formEditar.invalid) return this.errorDialogo.set('Revisa el nombre y el rol.');
    if (f.rol === 'ENTRENADOR' && !f.rama) return this.errorDialogo.set('Elige la rama del entrenador.');
    const cuerpo: Record<string, unknown> = { nombre: f.nombre, rama: f.rol === 'ENTRENADOR' ? f.rama : null };
    if (u.id !== this.yo()) Object.assign(cuerpo, { rol: f.rol, activo: f.activo }); // nadie se quita su propio acceso
    this.ejecutar(this.http.patch<Usuario>(`${API}/usuarios/${encodeURIComponent(u.id)}`, cuerpo), () => {
      this.editando.set(null);
      this.cargar();
      this.avisar(`Cuenta de ${f.nombre} actualizada.`);
    });
  }

  // ---------- Contraseña ----------
  protected abrirClave(u: UsuarioLista): void {
    this.formClave.reset();
    this.abrir(() => this.cambiandoClave.set(u));
  }

  protected guardarClave(): void {
    const u = this.cambiandoClave();
    if (!u) return;
    if (this.formClave.invalid) {
      return this.errorDialogo.set('La contraseña debe tener al menos 12 caracteres, con mayúscula, minúscula y número.');
    }
    const { password } = this.formClave.getRawValue();
    this.ejecutar(this.http.patch<Usuario>(`${API}/usuarios/${encodeURIComponent(u.id)}`, { password }), () => {
      this.cambiandoClave.set(null);
      this.claveEntregada.set({ email: u.email, clave: password });
    });
  }

  protected copiar(texto: string): void {
    void navigator.clipboard?.writeText(texto).then(() => this.avisar('Copiado al portapapeles.'));
  }

  // ---------- Utilidades ----------
  private abrir(mostrar: () => void): void {
    this.errorDialogo.set(null);
    this.mensaje.set(null);
    mostrar();
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

  private avisar(texto: string): void {
    this.mensaje.set({ error: false, texto });
  }
}
