# Context: catalog

For contributors working inside `src/catalog/`. Public catalog reads,
admin catalog management, taxonomy (categories, tags, attributes),
images, and demo data.

## Mental model

```
Product ── belongs to ──> Category (leaf only)
Product ── M:N ─────────> Tag
Category ── 1:N ───────> CategoryAttribute (inherited by children)
CategoryAttribute ── 1:N ─> AttributeOption  (for select/multiselect)
Product ── 1:N ────────> ProductAttributeValue
Product ── 1:N ────────> ProductImage
```

Products live in **leaf** categories only. A category's effective
attribute set is the union of its own attributes and every ancestor's
attributes; `code` must be unique across that chain.

## Public surface

Driving facade: `CatalogFacade` in `ports/driving/facade.py`.

| Wire endpoint | Auth | Use case |
|---|---|---|
| `GET /catalog` | public | List active products (paginated, filterable) |
| `GET /catalog/random` | public | Random active products |
| `GET /catalog/{id}` | public | Product detail (active only) |
| `GET /catalog/categories/tree` | public | Active category tree |
| `GET /catalog/tags` | public | Active tags |
| `GET /catalog/admin/search` | `view_products` | Admin product search |
| `GET /catalog/admin/search/schema` | `view_products` | SmartTable schema |
| `GET /catalog/admin/products/{id}` | `view_products` | Admin detail (incl. inactive) |
| `POST /catalog` | `edit_products` | Create product (multipart) |
| `PUT /catalog/{id}` | `edit_products` | Update product |
| `DELETE /catalog/{id}` | `edit_products` | Delete product + images |
| `DELETE /catalog/{id}/images` | `edit_products` | Remove a single image |
| `GET/POST/PUT/DELETE /catalog/admin/categories[...]` | `view_category_tree` / `edit_taxonomy` | Tree, attributes, move |
| `GET/POST/PUT/DELETE /catalog/admin/tags[...]` | `view_category_tree` / `edit_taxonomy` | Tag CRUD |
| `POST /catalog/admin/demo-data` | `create_demo_data` | Idempotent demo generator |

Wire-level field shapes live in [../contract/public.md](../contract/public.md)
and [../contract/admin.md](../contract/admin.md).

## Invariants & gotchas

- **Public reads force `is_active = true`** in use cases and
  repositories. `is_active` query params from public clients are
  ignored. Inactive products return 404, not 403.
- **Leaf-only product assignment.** Moving a category that has
  products must reject the move if the target ceases to be a leaf or
  any descendant has products.
- **No move cycles.** A category move that would make the category its
  own ancestor is rejected by the use case.
- **Cascade delete on images, not products.** Deleting a product
  cascades to `product_images` (FK). Deleting a category with children
  or products is rejected.
- **Attribute `code` uniqueness.** Validated against the effective
  inherited chain on create AND update. The DB UNIQUE on
  `(category_id, code)` alone is not enough.
- **Required + select/multiselect validation.** Product attribute
  values must cover every required attribute in the effective set; the
  value of a `select` attribute must match a known option id.
- **Tags are global, not category-scoped.** A tag applies to any
  product regardless of category.
- **Demo generation must be idempotent.** Re-running it must not
  create duplicate categories/tags/attributes/products. Image bytes
  come from a local placeholder; no network calls.
- **Random products use `ORDER BY rand()`.** Acceptable for the
  template scale only. Larger catalogs need an indexed strategy.

## How-to recipes

### Add a new product field

1. Domain: extend `Product` aggregate in `domain/product_agg.py`.
2. Migration: add `migrations/00NN_<slug>.sql` with `ALTER TABLE
   products ADD COLUMN ...` (and a `.rollback.sql` if reversible).
3. ORM: add the column to `ProductModel`.
4. Mapper: update domain ↔ ORM in `ports/driven/sql_product_repo.py`.
5. Schemas: add the field to In/Out schemas in `ports/driving/schemas.py`.
6. UI: add the field to the admin form and SmartTable schema.
7. Apply locally: `python scripts/db_apply.py`.
8. Docs: update [../contract/admin.md](../contract/admin.md) and
   [../infra/mysql.md](../infra/mysql.md).

### Add a new attribute type

Supported now: `text`, `number`, `boolean`, `select`, `multiselect`,
`date`, `url`, `color`, `file`, `image`. New types extend
`ProductAttributeValue` storage columns (`value_text`, `value_number`,
`value_bool`, …). Add validation in the attribute-value use case and
the admin form widget.

## Pointers

- ORM: `src/catalog/adapters/driven/db/models.py`
- Public/admin routes: `src/catalog/adapters/driving/api.py`,
  `src/catalog/adapters/driving/admin.py`
- Demo data: `src/catalog/app/use_cases/create_demo_data_uc.py`
- Filters subsystem: [../subsystems/smart-filters.md](../subsystems/smart-filters.md)
- Taxonomy decisions: [../adr/0002-flat-taxonomy-with-inherited-attrs.md](../adr/0002-flat-taxonomy-with-inherited-attrs.md)
