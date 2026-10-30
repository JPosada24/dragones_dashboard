import { Routes } from '@angular/router';

import { requierePermiso, requiereSesion, soloInvitado } from './core/auth/guards';
import { SECCIONES } from './core/secciones';

const enConstruccion = () => import('./paginas/en-construccion').then((m) => m.EnConstruccionPage);

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
        loadComponent: enConstruccion,
      })),
      {
        path: 'notificaciones',
        title: 'Avisos · Dragones',
        data: { titulo: 'Avisos', subtitulo: 'Tus notificaciones del club' },
        loadComponent: () => import('./paginas/notificaciones/notificaciones').then((m) => m.NotificacionesPage),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
