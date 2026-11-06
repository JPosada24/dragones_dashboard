# 0014. Torneos realizados: contenido del sitio aparte de la operación de torneos

- **Estado:** aceptada

## Contexto

El sitio necesita una sección con los torneos que el club ya organizó, cada uno con su anuncio (el afiche con que se
promocionó). La tabla `torneos` ya existe, pero es la operación: cupos, clubes inscritos, pagos y auditoría. Muchos
torneos se jugaron antes de la plataforma y no están ahí.

## Decisión

- Tabla propia `torneos_realizados` (migración 0028), editada en **Perfil del club → Torneos realizados** con el
  permiso `club.editar`: nombre, fecha, lugar, reseña (resultados), anuncio, álbum de la galería (opcional) y si se
  publica.
- No se enlaza con `torneos`: así caben los torneos de antes de la plataforma, y borrar uno del sitio nunca toca
  equipos, pagos ni auditoría de la operación.
- El anuncio se guarda **entero** (sin recortar, porque lleva texto), re-codificado y sin metadatos, en dos tamaños
  (1920 px y 720 px). Se sirve en `/publico/torneos-realizados/{id}/anuncio` solo si el torneo está publicado y el
  sitio también.
- El álbum enlazado solo se expone al sitio si ese álbum se ve en la galería (publicado y con fotos). Si se borra el
  álbum, el enlace se quita solo (`ON DELETE SET NULL`).

## Consecuencias

- Los torneos de la plataforma también tienen anuncio (flyer, migración 0029), visible en el sitio solo mientras las
  inscripciones están abiertas. Al jugarse, **«Pasar a realizados»** copia nombre, fecha, lugar y flyer (a archivos
  nuevos: borrar uno no deja al otro sin imagen) a una ficha oculta, enlazada con `torneo_id` (único: una sola vez).
  Solo falta escribir los resultados y publicarla. Como crea contenido del sitio, exige `eventos.gestionar` y
  `club.editar`.
