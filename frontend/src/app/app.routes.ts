import { Route, Routes } from '@angular/router';

import { requierePermiso, requiereSesion, soloInvitado } from './core/auth/guards';
import { SECCIONES } from './core/secciones';

type Cargar = NonNullable<Route['loadComponent']>;

const enConstruccion: Cargar = () => import('./paginas/en-construccion').then((m) => m.EnConstruccionPage);

/** Pantallas ya construidas; las demás secciones muestran "en construcción". */
const PANTALLAS: Record<string, Cargar> = {
  '': () => import('./paginas/resumen/resumen').then((m) => m.ResumenPage),
  asistencia: () => import('./paginas/asistencia/asistencia').then((m) => m.AsistenciaPage),
};

export const routes: Routes = [
  {
    path: 'login',
    canActivate: [soloInvitado],
    title: 'Ingresar · Dragones',
    loadComponent: () => import('./paginas/login/login').then((m) => m.LoginPage),
  },
  {
    path: '',
    canActivate: [requiereSesion],
    canActivateChild: [requierePermiso],
    loadComponent: () => import('./layout/shell').then((m) => m.Shell),
    children: [
      // Cada sección del menú es una ruta; se reemplaza la pantalla provisional a medida que se construye.
      ...SECCIONES.map((s) => ({
        path: s.ruta,
        pathMatch: 'full' as const,
        title: `${s.etiqueta} · Dragones`,
        data: { permisos: s.permisos, titulo: s.titulo, subtitulo: s.subtitulo, descripcion: s.descripcion },
        loadComponent: PANTALLAS[s.ruta] ?? enConstruccion,
      })),
    ],
  },
  { path: '**', redirectTo: '' },
];
