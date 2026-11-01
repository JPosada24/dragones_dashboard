# 0002. Tablas de evidencia de solo agregar (trigger en PostgreSQL)

- **Estado:** aceptada

## Contexto

Hay dinero de por medio (abonos, pagos de multas, rifas y torneos) y decisiones que afectan a familias (prórrogas, expulsiones). Si un registro se puede editar o borrar, nadie puede confiar en él.

## Decisión

La auditoría, los pagos, las prórrogas y las actas de sorteo son de solo agregar: la función `solo_agregar()` de PostgreSQL rechaza UPDATE y DELETE. Un error se corrige con un movimiento nuevo (una anulación con monto negativo que apunta al original). La única excepción es la purga de un alumno (`SET LOCAL dragones.purga`), que nunca aplica a la auditoría.

## Consecuencias

- La regla vive en la base: ni un error en el código ni alguien con acceso a la API la puede saltar.
- Los saldos se calculan sumando movimientos; nunca se «arregla» un número a mano.
- Las pruebas construyen el esquema con las migraciones reales para probar también los triggers.
