# 0004. Access token en memoria y refresh token rotativo con detección de reuso

- **Estado:** aceptada

## Contexto

El panel lo usan entrenadores desde celulares compartidos o propios. Un token robado no debe servir por días.

## Decisión

El access token (JWT, 15 minutos) vive solo en memoria del navegador, nunca en localStorage. El refresh token va en una cookie HttpOnly, se rota en cada uso y, si se presenta uno ya usado, se revoca toda la familia de sesiones (señal de robo). Cambiar la contraseña o el rol sube `credenciales_version` e invalida los tokens al instante. Bloqueo por cuenta tras 5 fallos y límite por IP.

## Consecuencias

- Un XSS no puede leer el refresh token; un token robado vale minutos.
- Recargar la página pide un access token nuevo con la cookie (una petición más).
- La clave de firma se puede rotar sin cerrar sesiones (`SECRET_KEY_ANTERIOR`).
