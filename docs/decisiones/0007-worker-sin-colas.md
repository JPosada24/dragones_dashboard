# 0007. Worker con tareas idempotentes y advisory locks (sin Celery ni Redis)

- **Estado:** aceptada

## Contexto

Hay trabajo que nadie lanza a mano: cerrar la asistencia y generar multas, vencer inscripciones, detectar mora, programar entrenamientos, enviar correos. El volumen es pequeño (un club).

## Decisión

Un proceso `worker` corre cada tarea por intervalo. Cada tarea es idempotente (repetirla no duplica nada) y toma un `pg_try_advisory_xact_lock` para que dos workers no la corran a la vez. Deja su latido en la base (`/salud/worker`).

## Consecuencias

- Sin infraestructura extra: PostgreSQL ya da los locks.
- Si el worker estuvo apagado, al volver se pone al día solo.
- Si el volumen creciera mucho, las tareas ya están aisladas para moverlas a una cola.
