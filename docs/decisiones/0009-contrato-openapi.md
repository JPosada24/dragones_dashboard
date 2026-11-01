# 0009. Tipos del frontend generados del contrato OpenAPI

- **Estado:** aceptada

## Contexto

Las interfaces de TypeScript escritas a mano se desalineaban de la API sin que nadie lo notara (la API devolvía campos que el frontend no conocía y el frontend enviaba valores que la API no aceptaba).

## Decisión

Los valores válidos del dominio son `Literal` en el backend (verificados contra los `CHECK` de la base). `app.scripts.openapi` exporta el contrato y `openapi-typescript` genera `esquema.ts`; los modelos del frontend son alias de esos tipos. El CI falla si el contrato guardado o los tipos no coinciden con la API.

## Consecuencias

- Un cambio en la API que rompe el frontend se ve al compilar, no en producción.
- Hay que regenerar el contrato al cambiar la API (dos comandos, documentados).
- Al activarlo aparecieron envíos sueltos reales (rama nula, tipo de documento libre) y se corrigieron.
