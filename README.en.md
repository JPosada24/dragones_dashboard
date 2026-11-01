# Dragones — Management platform for a volleyball club

[![CI](https://github.com/JPosada24/dragones_dashboard/actions/workflows/ci.yml/badge.svg)](https://github.com/JPosada24/dragones_dashboard/actions/workflows/ci.yml)

*[Leer en español](README.md)*

A production system for a real sports club in Colombia: students and guardians, yearly enrollment with partial
payments and deadlines, attendance with automatic fines, overdue-debt detection, raffles with a verifiable draw,
tournaments with external clubs, email and WhatsApp notices, and a public website fed by the same API. All data in
this repository and its tests is fictitious.

> **Why is the code in Spanish?** The club, its rules and its users speak Spanish, and several business concepts have
> no exact English equivalent (*paz y salvo*, *acudiente*, *abono*). Following Domain-Driven Design's *ubiquitous
> language*, business names stay in Spanish while technical names keep their usual English form. See
> [ADR 0001](docs/decisiones/0001-dominio-en-espanol.md).

## Highlights

- **Evidence that cannot be edited.** Payments, extensions, raffle draw records and the audit log are append-only,
  enforced by a PostgreSQL trigger. Mistakes are fixed with a reversing entry, never with UPDATE or DELETE.
- **Encrypted personal data with blind indexes.** ID numbers and uploaded files are encrypted at rest (Fernet); an
  HMAC blind index allows exact lookups and duplicate detection without decryption. Keys can be rotated
  (`MultiFernet` + a re-encryption script).
- **Sessions done right.** 15-minute JWT kept in memory only; rotating refresh token in an HttpOnly cookie with
  **reuse detection**; password or role changes revoke tokens instantly; per-account lockout plus a per-IP limiter
  shared across processes.
- **Authorization tested from the negative side.** Every route declares its permission and every service enforces
  scope; tests cover what each role **cannot** do. Foreign resources answer 404.
- **Frontend types generated from the OpenAPI contract.** Domain values are `Literal` types in the backend (checked
  against the database `CHECK` constraints); CI fails if the API and the frontend drift apart.
- **Idempotent background worker** using PostgreSQL advisory locks (no Celery/Redis needed at this scale), with a
  heartbeat exposed for uptime monitoring.
- **Operations.** Caddy with automatic HTTPS and a strict CSP, encrypted daily backups with an **asymmetric** key
  (the server cannot read its own backups) and a tested restore path, JSON logs with request IDs, optional
  Sentry/GlitchTip with PII scrubbing.
- **Supply chain.** Hash-pinned Python dependencies, `pip-audit`, `npm audit`, Trivy image scanning, gitleaks,
  Dependabot.

## Stack

FastAPI · SQLAlchemy 2 · Alembic · Pydantic v2 · PostgreSQL 16 · Angular 22 (standalone, signals, zoneless) ·
Vitest · Docker Compose · Caddy · GitHub Actions.

## Architecture and decisions

See the diagram in the [Spanish README](README.md#arquitectura) and the architecture decision records in
[`docs/decisiones/`](docs/decisiones/README.md).

## Running it

```bash
cp .env.example .env    # then replace every value marked "CAMBIA"
docker compose up --build
```

Panel at <http://localhost:4300>, interactive API docs at <http://localhost:8000/api/docs>. Production deployment:
[`docs/despliegue.md`](docs/despliegue.md).

## License

[MIT](LICENSE) © 2026 Julian Posada
