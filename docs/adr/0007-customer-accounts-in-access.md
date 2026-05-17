# 0007 — Customer accounts in the access context
Status: accepted
Date: 2026-05-17

## Context

E-commerce platform requires authenticated customer accounts (register,
password recovery) alongside existing admin users. Question: new `customers/`
context or extend `access/`?

## Decision

Customer accounts live in the **access** context. Both users and customers
share auth infrastructure (JWT issuance, token invalidation, recovery codes).
Splitting them creates coupling cost (shared token logic, permission gate)
without benefit at this scale.

## Consequences

- + Single JWT issuance + permission-gate code path.
- + Shared recovery-code pipeline, email sender infra.
- + Cross-context call from `ordering` still goes through ACL in `ports/driven/`.
- − `access` now owns two aggregates (`User`, `Customer`) with shared lifecycle
  (authentication). Acceptable since both are auth subjects.

## Alternatives considered

- New `customers/` context — introduces coupling on JWT/token-invalidation logic.
- Auth federation — out of scope; assume customers are local.
