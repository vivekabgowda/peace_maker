# Coding Standards

Enforced automatically in CI and (optionally) via pre-commit/Husky. These notes
capture the intent behind the tooling.

## Principles

- **Clean Architecture & SOLID.** Dependencies point inward: `domain` → nothing;
  `application` (services) → domain ports; `infrastructure` (repos/adapters) →
  implements ports; `api` (routers) → thin, no business logic.
- **Type safety end to end.** MyPy strict on the backend; TypeScript strict on
  the frontend. No `any`/`# type: ignore` without a reason.
- **Small, single-responsibility modules.** Each bounded context is
  independently testable and extractable.
- **Tests ship with code.** New behavior comes with unit and/or integration
  tests. Risk-adjacent code (later sprints) is release-gated by its test suite.

## Backend (Python)

| Tool | Rule |
|------|------|
| Ruff | Lint (pycodestyle, pyflakes, isort, bugbear, security, pyupgrade, naming). Line length 100. |
| Black | Formatting, line length 100, target py312. |
| MyPy | `strict = true`. Public functions are fully typed. |
| Pytest | `asyncio_mode = auto`; unit tests are I/O-free; integration tests marked `@pytest.mark.integration`. |

Conventions:
- Modules/functions `snake_case`; classes `PascalCase`.
- Money is `Decimal`/`NUMERIC`, never `float`.
- Timestamps are timezone-aware UTC; render IST at the edge.
- Raise typed domain errors (`app.core.errors`), never bare `HTTPException` from
  services.
- Repositories are the only code that touches the database for their table.

## Frontend (TypeScript / React)

| Tool | Rule |
|------|------|
| ESLint | `next/core-web-vitals` + `next/typescript` + Prettier compatibility. 0 warnings in CI. |
| Prettier | Single quotes, trailing commas, width 100, Tailwind class sorting. |
| TypeScript | `strict`, `noUncheckedIndexedAccess`, `noUnusedLocals/Parameters`. |
| Vitest | Unit tests colocated as `*.test.ts(x)`. |

Conventions:
- Components `PascalCase.tsx`; hooks `useCamelCase.ts`.
- `features/` mirror backend `modules/`.
- Server Components by default; add `'use client'` only where interactivity/state
  is needed.
- API types are generated from the backend OpenAPI schema (from Sprint 2); do not
  hand-maintain duplicates.
- Color is never the only signal (accessibility): pair semantic colors with an
  icon or label.

## Git & reviews

- **Conventional Commits** (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`,
  `chore:`).
- Branch naming: `type/scope-short-desc`.
- Every PR must pass CI (lint, type, test, build, Docker build) before merge.
- Keep PRs small and single-purpose; update docs/ADRs when architecture changes.

## Definition of Done (per change)

- [ ] Meets acceptance criteria; typed end to end.
- [ ] Unit/integration tests added; all gates green locally and in CI.
- [ ] Structured logging/metrics added where relevant.
- [ ] Docs/OpenAPI updated; no secrets committed.
