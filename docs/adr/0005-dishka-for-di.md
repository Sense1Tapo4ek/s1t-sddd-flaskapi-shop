# 0005 — Dishka for dependency injection
Status: accepted
Date: 2026-05-15

## Context

S-DDD layering requires use cases to depend on Protocols/ABCs, not
concrete repos. Hand-wiring at every Flask handler is repetitive and
error-prone. The container must support per-request scope (SQLAlchemy
session) and integrate with Flask blueprints.

## Decision

Use Dishka (`dishka.integrations.flask`). Each context owns
`provider.py` with its bindings; `src/root/container.py` registers
them all into one container. Handlers receive deps via `@inject` +
`FromDishka[T]`. Concrete-to-interface mapping
(`provide(SqlProductRepo, provides=IProductRepo)`) lives ONLY in
providers.

## Consequences

- + Use cases and facades are constructor-injectable, framework-free.
- + Per-request scope handles the SQLAlchemy session lifecycle.
- + Provider files document each context's wiring in one place.
- − Smaller ecosystem footprint than `dependency-injector`.
- − `@inject` must be innermost on Flask handlers — easy to get wrong.

## Alternatives considered

- `dependency-injector` — heavier API, less ergonomic with type hints.
- Module-level singletons — can't model request scope; breaks tests.
- Hand-passing factories — explodes handler signatures.
