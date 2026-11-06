import { ComponentFixture, TestBed } from '@angular/core/testing';

import { AuthService } from '../core/auth/auth.service';
import { Rol, Usuario } from '../core/modelos';
import { TutorialService } from '../core/tutorial.service';
import { Ayuda, AyudaBoton } from './ayuda';

const AYUDA: Ayuda = {
  titulo: 'Cómo funciona',
  pasos: [
    { titulo: 'Para todos', texto: 'Uno' },
    { titulo: 'Solo staff', texto: 'Dos', permisos: ['alumnos.ver_todos'] },
  ],
  nota: '<b>nota</b>',
};

describe('AyudaBoton', () => {
  let fixture: ComponentFixture<AyudaBoton>;

  function crear(permisos: string[], rol: Rol = 'MIEMBRO') {
    const usuario: Usuario = { id: 'u', email: 'x@club.com', nombre: 'X', rol, activo: true, tutorial_visto: true, permisos };
    TestBed.inject(AuthService).usuario.set(usuario);
    fixture = TestBed.createComponent(AyudaBoton);
    fixture.componentRef.setInput('ayuda', AYUDA);
    fixture.detectChanges();
  }

  const el = () => fixture.nativeElement as HTMLElement;

  async function abrir() {
    el().querySelector<HTMLButtonElement>('button[aria-label="Cómo funciona"]')!.click();
    await fixture.whenStable();
    fixture.detectChanges();
  }

  it('abre la explicación y muestra cada paso solo a quien le corresponde', async () => {
    crear(['alumnos.ver_propios']);
    expect(el().querySelector('dialog')).toBeNull();
    await abrir();
    const texto = el().querySelector('dialog')!.textContent ?? '';
    expect(texto).toContain('Para todos');
    expect(texto).not.toContain('Solo staff');
    expect(el().querySelector('.nota-ayuda')?.textContent).toBe('<b>nota</b>'); // texto, nunca HTML
  });

  it('el staff ve también sus pasos y "Entendido" cierra', async () => {
    crear(['alumnos.ver_todos']);
    await abrir();
    expect(el().querySelector('dialog')!.textContent).toContain('Solo staff');
    [...el().querySelectorAll('button')].find((b) => b.textContent?.includes('Entendido'))!.click();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(el().querySelector('dialog')).toBeNull();
  });

  it('el staff puede volver a ver el recorrido del panel; la familia no lo ve', async () => {
    crear(['alumnos.ver_propios']);
    await abrir();
    expect(el().textContent).not.toContain('Ver el recorrido');

    TestBed.resetTestingModule();
    crear(['alumnos.ver_todos'], 'ADMIN');
    await abrir();
    [...el().querySelectorAll('button')].find((b) => b.textContent?.includes('Ver el recorrido'))!.click();
    await fixture.whenStable();
    fixture.detectChanges();
    expect(TestBed.inject(TutorialService).activo()).toBe(true);
    expect(el().querySelector('dialog')).toBeNull(); // la ayuda se cierra para dar paso al recorrido
  });
});
