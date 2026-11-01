# 0006. El dueño es SuperAdmin; el Entrenador no hereda acceso total

- **Estado:** aceptada

## Contexto

El dueño del club es también el entrenador principal y hace de todo. Los entrenadores asistentes cambian.

## Decisión

El dueño usa el rol SuperAdmin. El rol Entrenador es para asistentes: ve ambas ramas, marca asistencia e inscribe con abonos, pero no cobra multas ni rifas, no ve el documento completo, no concede prórrogas ni cambia el horario. Los permisos viven en la base y se verifican siempre en el servidor; el frontend solo oculta botones.

## Consecuencias

- Un asistente nuevo no hereda acceso total por accidente.
- Cada regla tiene su prueba, incluida la de qué rol **no** puede.
- Ampliar el rol Entrenador «para que pueda todo» está descartado: para eso está SuperAdmin.
