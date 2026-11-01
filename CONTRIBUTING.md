# Cómo se trabaja en este repositorio

## Flujo

1. Cada cambio sale de una rama corta desde `main`: `feat/rifas-reporte`, `fix/cierre-asistencia`, `docs/readme`.
2. Se abre un pull request hacia `main`. El CI debe pasar completo (pruebas, lint, auditorías, Trivy, gitleaks).
3. `main` está protegida: no se empuja directo y no se mezcla con el CI en rojo (ver «Protección de `main`»).
4. Se mezcla con *squash*: un commit por cambio, con el título del pull request.

## Mensajes de commit (Conventional Commits)

```
<tipo>(<alcance opcional>): <qué cambia, en imperativo y en español>

<por qué cambia y qué hay que saber; opcional>
```

| Tipo | Cuándo |
|---|---|
| `feat` | Funcionalidad nueva para el club |
| `fix` | Corrección de un error |
| `refactor` | Cambio interno sin cambiar el comportamiento |
| `test` | Solo pruebas |
| `docs` | Solo documentación |
| `build` | Dependencias, Docker, compilación |
| `ci` | Flujos de GitHub Actions |
| `chore` | Mantenimiento que no encaja en los anteriores |

Un cambio que rompe algo (por ejemplo, una ruta de la API que cambia) lleva `!` (`feat(api)!: …`) y un párrafo
`BREAKING CHANGE:` que explique cómo adaptarse.

## Versiones

- Se sigue [SemVer](https://semver.org/lang/es/): `MAYOR.MENOR.PARCHE`.
- Cada versión es una etiqueta anotada (`git tag -a v1.2.0 -m "…"`) y una entrada en `CHANGELOG.md`.

## Antes de abrir el pull request

```powershell
docker compose run --rm --user root api sh -c "pip install -q --require-hashes -r requirements-dev.txt && ruff check . && pytest"
cd frontend; npm run lint; npx ng test --watch=false --coverage
```

Si cambiaste la API (rutas o esquemas), regenera el contrato y los tipos del frontend:

```bash
docker compose exec -T api python -m app.scripts.openapi > frontend/openapi/openapi.json
cd frontend && npm run api:tipos
```

Si cambiaste dependencias de Python, edita `requirements.in` / `requirements-dev.in` y vuelve a fijarlas con hashes:

```powershell
docker compose run --rm --user root api sh -c "pip install -q pip-tools && pip-compile --generate-hashes --allow-unsafe --strip-extras -o requirements.txt requirements.in && pip-compile --generate-hashes --allow-unsafe --strip-extras -o requirements-dev.txt requirements-dev.in"
```

## Protección de `main` (configuración única en GitHub)

*Settings → Rules → Rulesets → New branch ruleset*, objetivo `main`:

- **Restrict deletions** y **Block force pushes**.
- **Require a pull request before merging** (permite *squash*).
- **Require status checks to pass**: `Pruebas (pytest + PostgreSQL)`, `Frontend (auditoría, lint, compilación y pruebas)`,
  `Imagen Docker de la API (Trivy)` y `Búsqueda de secretos (gitleaks)`.

Además, en *Settings → Code security*: **Dependabot alerts**, **Dependabot security updates**, **Secret scanning** y
**Push protection** activados.

## Reglas que no se negocian

Están en `CLAUDE.md` («Seguridad»): autorización en el servidor, alcance en el servicio, nada de SQL armado con texto,
datos sensibles cifrados, tablas de evidencia de solo agregar y una prueba por cada regla nueva (también la de qué rol
**no** puede). Nunca se suben secretos ni datos reales del club: el repositorio es público.
