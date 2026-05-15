# 0002 — Category tree + inherited attributes; tags orthogonal
Status: accepted
Date: 2026-05-15

## Context

Forks cover furniture, clothing, food, electronics. Each needs
different product fields and navigation. A hard-coded `Product`
schema cannot cover them; duplicating fields per category balloons.

## Decision

- Category tree via self-FK; products belong to LEAF categories only.
- `category_attributes` define inherited fields; descendants see the
  union. Attribute `code` unique across the effective chain.
- Tags + `product_tags` provide category-independent labels.
- Attribute types stored in `product_attribute_values` with typed
  columns: `text`, `number`, `boolean`, `select`, `multiselect`,
  `date`, `url`, `color`, `file`, `image`.

## Consequences

- + One schema fits every shop type; variability lives in data.
- + Public clients build faceted storefronts from category/tag/attr.
- − Inheritance requires ancestor-chain traversal per request.
  Cache needed for very large trees.
- − Migration from flat catalog required idempotent compat patches.

## Alternatives considered

- Per-category product tables — schema explosion.
- Single JSON attribute blob — breaks filter/validation/UI.
- Flat categories — real shops have 2-3 levels.
- Tags inside the tree — conflates orthogonal axes.
