# 0008. Eliminar una cuenta conserva la evidencia

- **Estado:** aceptada

## Contexto

El SuperAdmin necesita quitar cuentas (un asistente que se va, una cuenta de familia equivocada), pero pagos, asistencias y la auditoría guardan quién los registró.

## Decisión

Eliminar no borra la fila: libera el correo (`eliminado-<id>@usuarios.invalid`), pone una contraseña aleatoria, invalida tokens y sesiones, desvincula al alumno o acudiente y la oculta del panel. Se conserva el nombre para que el historial siga diciendo quién hizo qué.

## Consecuencias

- La evidencia de dinero no se pierde y la auditoría no se toca.
- El correo se puede reutilizar para una cuenta nueva.
- Para un retiro temporal sigue existiendo «Desactivar».
