import { Route, Routes } from '@angular/router';

import { requierePermiso, requiereSesion, soloInvitado } from './core/auth/guards';
import { AYUDAS } from './core/ayudas';
import { SECCIONES } from './core/secciones';

type Cargar = NonNullable<Route['loadComponent']>;

const enConstruccion: Cargar = () => import('./paginas/en-construccion').then((m) => m.EnConstruccionPage);

/** Pantallas ya construidas; las demás secciones muestran "en construcción". */
const PANTALLAS: Record<string, Cargar> = {
  '': () => import('./paginas/resumen/resumen').then((m) => m.ResumenPage),
  asistencia: () => import('./paginas/asistencia/asistencia').then((m) => m.AsistenciaPage),
  alumnos: () => import('./paginas/alumnos/alumnos').then((m) => m.AlumnosPage),
  multas: () => import('./paginas/multas/multas').then((m) => m.MultasPage),
  rifas: () => import('./paginas/rifas/rifas').then((m) => m.RifasPage),
  'rifas/sorteo': () => import('./paginas/rifas/sorteo/sorteo').then((m) => m.SorteoPage),
  usuarios: () => import('./paginas/usuarios/usuarios').then((m) => m.UsuariosPage),
  torneos: () => import('./paginas/torneos/torneos').then((m) => m.TorneosPage),
  configuracion: () => import('./paginas/configuracion/configuracion').then((m) => m.ConfiguracionPage),
  avisos: () => import('./paginas/avisos/avisos').then((m) => m.AvisosPage),
  'perfil-club': () => import('./paginas/perfil-club/perfil-club').then((m) => m.PerfilClubPage),
  asistente: () => import('./paginas/asistente/asistente').then((m) => m.AsistentePage),
  'alumnos/inscripciones': () => import('./paginas/inscripciones/inscripciones').then((m) => m.InscripcionesPage),
};

export const routes: Routes = [
  {
    // Sitio público del club: sin sesión.
    path: 'sitio',
    title: 'Club Deportivo Dragones',
    loadComponent: () => import('./paginas/sitio/sitio').then((m) => m.SitioPage),
  },
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
        data: {
          permisos: s.permisos, titulo: s.titulo, subtitulo: s.subtitulo, descripcion: s.descripcion,
          ayuda: AYUDAS[s.ruta],
        },
        loadComponent: PANTALLAS[s.ruta] ?? enConstruccion,
      })),
    ],
  },
  { path: 'inscripciones', redirectTo: 'alumnos/inscripciones' }, // enlaces viejos
  { path: '**', redirectTo: '' },
];
