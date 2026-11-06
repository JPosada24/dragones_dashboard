# 0013. Admin con todo menos cuentas, y permisos ajustables por persona

- **Estado:** aceptada (amplía la [0006](0006-roles.md))

## Contexto

El Admin coordina el club a diario y necesitaba casi todo (anular pagos, confirmar expulsiones, parámetros,
reportes, habeas data). Al mismo tiempo, a veces una persona concreta necesita algo distinto a su rol: un
entrenador que vea los reportes, o un Admin al que no se le quiere dejar anular pagos. Cambiar el rol completo
para eso afectaría a todos los que lo tienen.

## Decisión

- El rol **Admin** tiene todos los permisos **menos** administrar cuentas (`usuarios.gestionar`, `usuarios.eliminar`)
  y los propios de una familia (`alumnos.ver_propios`, `asistencia.marcar_propia`).
- El SuperAdmin puede **dar o quitar** permisos a una persona con rol Admin o Entrenador
  (tabla `usuarios_permisos`, migración 0027). Los permisos efectivos son los del rol + los dados − los quitados,
  calculados en `Usuario.permisos_codigos`, que es lo que consultan todas las rutas.
- **No se le dan a nadie** los permisos de cuentas: quien los tuviera podría darse acceso total a sí mismo.
  Tampoco se ajusta al SuperAdmin (siempre lo tiene todo), a una cuenta de familia ni a la propia cuenta.
- Cambiar el rol de una persona borra sus ajustes: queda con los del rol nuevo.
- La matriz de roles se ve en **Usuarios** (`GET /usuarios/roles`), no en Configuración.

## Consecuencias

- Un ajuste aplica en la siguiente petición, sin cerrar la sesión de la persona (los permisos se leen de la base en
  cada petición); su menú se actualiza al renovar el token o recargar.
- Cada ajuste queda en la auditoría (`usuario.permisos`, con lo dado y lo quitado antes y después).
- Los avisos al staff siguen yendo por rol (SuperAdmin, Admin y entrenadores), no por permisos ajustados.
- Sigue en pie lo de la 0006: no se amplía el rol Entrenador; si un asistente necesita más, se le da a él.
