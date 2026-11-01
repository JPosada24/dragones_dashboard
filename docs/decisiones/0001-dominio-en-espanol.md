# 0001. El lenguaje del negocio en español

- **Estado:** aceptada

## Contexto

El club, sus reglas y sus usuarios hablan español, y varios conceptos no tienen traducción exacta (paz y salvo, acudiente, abono, prórroga, talonario). El framework y las librerías están en inglés.

## Decisión

Tablas, columnas, rutas, servicios y variables de negocio van en español; lo técnico conserva su nombre en inglés (`Depends`, `select`, `signal`). Es el «lenguaje ubicuo» de Domain-Driven Design: el código usa las mismas palabras que la gente del club.

## Consecuencias

- Sin traducciones ambiguas entre lo que pide el club y lo que dice el código.
- Un lector que no hable español necesita este registro y el README para orientarse.
- La regla es la consistencia: nunca se mezclan los dos idiomas para el mismo concepto.
