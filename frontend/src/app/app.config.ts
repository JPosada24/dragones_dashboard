import { registerLocaleData } from '@angular/common';
import { provideHttpClient, withFetch, withInterceptors } from '@angular/common/http';
import localeEsCo from '@angular/common/locales/es-CO';
import {
  ApplicationConfig, LOCALE_ID, inject, provideAppInitializer, provideBrowserGlobalErrorListeners,
} from '@angular/core';
import { provideRouter, withComponentInputBinding, withInMemoryScrolling } from '@angular/router';

import { routes } from './app.routes';
import { authInterceptor } from './core/auth/auth.interceptor';
import { AuthService } from './core/auth/auth.service';

registerLocaleData(localeEsCo);

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    // anchorScrolling: los enlaces con fragmento del sitio público (/sitio#galeria) bajan a su sección.
    provideRouter(routes, withComponentInputBinding(), withInMemoryScrolling({ anchorScrolling: 'enabled' })),
    provideHttpClient(withFetch(), withInterceptors([authInterceptor])),
    // Antes de la primera pantalla: si la cookie de refresh sigue viva, la sesión continúa.
    provideAppInitializer(() => inject(AuthService).restaurarSesion()),
    { provide: LOCALE_ID, useValue: 'es-CO' },
  ],
};
