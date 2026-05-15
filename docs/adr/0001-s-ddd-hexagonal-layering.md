# 0001 — S-DDD hexagonal layering with one facade per context
Status: accepted
Date: 2026-05-15

## Context

Forkable e-commerce: clones must add a context or swap a piece without
rewriting the rest. Flat Flask apps couple routes, ORM, and business
rules through module imports.

## Decision

Organize `src/` as bounded contexts (`catalog`, `ordering`, `access`,
`system`, `shared`, `root`). Each follows the four-layer S-DDD shape:
`domain/`, `app/`, `ports/{driving,driven}/`, `adapters/{driving,driven}/`.
Imports flow inward. Each context exposes ONE driving facade — no
per-actor split at this scale.

## Consequences

- + Adding a context = copy the layout, fill layers, register provider.
- + Domain stays framework-free and unit-testable.
- + Cross-context coupling forced through ACLs in `ports/driven/`.
- − Single facade grows over time; revisit if it exceeds ~20 methods.
- − Strict imports require discipline.

## Alternatives considered

- Flat Flask app — couples HTTP/ORM/rules.
- Per-actor facade split — ceremony without benefit at current scale.
- Full microservices — wrong fit for single-process / CPanel target.
