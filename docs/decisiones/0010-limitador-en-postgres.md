# 0010. Limitador de intentos en PostgreSQL en vez de Redis

- **Estado:** aceptada

## Contexto

El límite de logins fallidos y de envíos del sitio público vivía en la memoria de cada proceso: con varios procesos de la API, cada uno contaba por su lado y el límite se multiplicaba.

## Decisión

Los intentos se guardan en la tabla `intentos` (con el SHA-256 de la IP, no la IP) y se cuentan en una ventana deslizante con su propia conexión, para que un fallo cuente aunque la petición termine en error. El worker borra lo de más de un día.

## Consecuencias

- Un límite real con N procesos, sin sumar Redis a la infraestructura.
- Una consulta indexada por intento: irrelevante para el volumen de un club.
- Si llegara Redis por otra razón, la interfaz `LimitadorFallos` no cambia.
