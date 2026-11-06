import { HttpErrorResponse } from '@angular/common/http';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';

import { AuthService, rutaSegura } from '../../core/auth/auth.service';
import { DemoService, InfoDemo } from '../../core/demo.service';
import { NOMBRE_ROL } from '../../core/modelos';

@Component({
  selector: 'app-login',
  imports: [ReactiveFormsModule],
  templateUrl: './login.html',
  styleUrl: './login.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LoginPage {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly ruta = inject(ActivatedRoute);

  protected readonly enviando = signal(false);
  protected readonly error = signal<string | null>(null);
  protected readonly expirada = this.ruta.snapshot.queryParamMap.has('expirada');
  private readonly demo = inject(DemoService);
  /** En el demo público: las cuentas de prueba, para entrar con un clic. */
  protected readonly infoDemo = this.demo.info;
  protected readonly nombreRol = NOMBRE_ROL;

  constructor() {
    this.demo.cargar();
  }

  protected entrarComo(cuenta: InfoDemo['cuentas'][number], clave: string): void {
    this.form.setValue({ email: cuenta.email, password: clave });
    this.ingresar();
  }

  protected readonly form = inject(NonNullableFormBuilder).group({
    email: ['', [Validators.required, Validators.email, Validators.maxLength(254)]],
    password: ['', [Validators.required, Validators.maxLength(128)]],
  });

  protected ingresar(): void {
    if (this.form.invalid || this.enviando()) {
      this.form.markAllAsTouched();
      return;
    }
    this.enviando.set(true);
    this.error.set(null);
    const { email, password } = this.form.getRawValue();
    this.auth.login(email, password).subscribe({
      next: () => {
        void this.router.navigateByUrl(rutaSegura(this.ruta.snapshot.queryParamMap.get('volver')));
      },
      error: (e: unknown) => {
        this.enviando.set(false);
        this.form.controls.password.reset();
        this.error.set(mensajeDeError(e));
      },
    });
  }
}

function mensajeDeError(e: unknown): string {
  if (e instanceof HttpErrorResponse) {
    if (e.status === 401) return 'Correo o contraseña incorrectos.';
    if (e.status === 429) return 'Demasiados intentos fallidos. Espera unos minutos e intenta de nuevo.';
    if (e.status === 422) return 'Revisa el correo: no tiene un formato válido.';
    if (e.status === 0) return 'No hay conexión con el servidor.';
  }
  return 'No se pudo iniciar sesión. Intenta de nuevo.';
}
