import type { components } from './esquema';

/**
 * Un esquema de la API por su nombre en el backend (Pydantic), p. ej. `Esquema<'AlumnoOut'>`.
 *
 * `esquema.ts` se genera del contrato OpenAPI (`openapi/openapi.json`); no se edita a mano:
 *   docker compose exec -T api python -m app.scripts.openapi > openapi/openapi.json && npm run api:tipos
 * El CI falla si el contrato del backend y estos tipos no coinciden.
 */
export type Esquema<N extends keyof components['schemas']> = components['schemas'][N];
