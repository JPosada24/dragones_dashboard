# 0012. Rifas sin compradores y sorteo verificable

- **Estado:** aceptada

## Contexto

Llevar el nombre del comprador de cada boleta era trabajo que nadie hacía. Lo que importa es si el talonario del alumno está pagado y que el sorteo sea transparente.

## Decisión

El talonario (20 boletas) es del alumno y se paga completo o por abonos. Solo entran al sorteo los talonarios pagados al 100 %. El ganador lo elige el servidor con `secrets.choice` y cada jugada deja un acta inmutable con la lista de participantes y su SHA-256; una boleta no gana dos veces en la misma rifa.

## Consecuencias

- Paz y salvo simple: talonario pagado.
- Cualquiera puede verificar la huella del acta contra la lista publicada.
- La animación del sorteo es solo visual.
