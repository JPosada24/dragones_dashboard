# Dragones — frontend (Angular 22)

Interfaz del club: componentes standalone, signals, detección de cambios OnPush y sin zone.js.
El diseño (colores, fuentes, escudo) sale del prototipo `Dashboard Dragones (standalone).html`.

## Correr

Desde la raíz del proyecto (todo en Docker):

```powershell
docker compose up -d frontend        # http://localhost:4300
docker compose exec frontend npx ng test --watch=false
docker compose exec frontend npx ng build
```

En desarrollo `/api` se reenvía a la API (`proxy.conf.json`): el navegador ve un solo origen, así que la cookie de
sesión funciona sin CORS. En producción lo hará el proxy (Caddy).

## Estructura

```
src/app/
  core/          sesión (auth.service, interceptor, guards), modelos de la API, mapa de secciones
  layout/        marco: barra lateral, barra superior, pestañas del celular
  paginas/       una carpeta por pantalla (login, notificaciones, …)
src/styles.scss  tokens de diseño y utilidades compartidas
public/          escudo y fuentes servidas por el propio sitio
```

## Seguridad

- El access token vive **solo en memoria**; el refresh token es una cookie HttpOnly que JavaScript no ve.
- El interceptor solo envía el token a nuestra API y renueva la sesión una vez ante un 401.
- Los guards solo ordenan la navegación: **la autorización real la hace siempre el servidor**.
- Textos de la API siempre con interpolación (`{{ }}`), nunca como HTML.
- La ruta para volver tras el login solo acepta rutas internas (sin redirecciones abiertas).
