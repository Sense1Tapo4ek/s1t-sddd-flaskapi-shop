# Catalog Taxonomy Plan

This document describes the planned catalog upgrade for the shop template:
category tree management, tags, inherited category attributes, product
classification, admin UI pages, public API support, migration, and tests.

The goal is to turn the current flat product catalog into a reusable foundation
for many shop types without breaking the existing S-DDD architecture.

---

## Goal

Make the catalog universal enough for real shops where product structure depends
on category.

Target behavior:

- Products belong to exactly one final category.
- Categories form a tree.
- Parent categories define fields that child categories inherit.
- Tags provide flexible marketing or grouping labels outside the category tree.
- Admin users can manage the structure through a graphical interface.
- Public API clients can build a storefront from categories, tags, filters, and
  product attributes.

Example:

```text
Catalog
├── Clothing
│   ├── Women
│   │   ├── Dresses
│   │   └── Skirts
│   └── Men
├── Shoes
│   ├── Sneakers
│   └── Boots
└── Accessories
```

`Clothing` can define inherited fields such as `size`, `color`, and `material`.
`Dresses` can add its own fields such as `length` and `season`.

---

## Current State

The current catalog is intentionally simple:

- `Product` has `id`, `title`, `price`, `description`, `is_active`,
  `created_at`, and `images`.
- Product images are stored in `product_images`.
- Admin products are managed through `/admin/products/`.
- The admin product table uses `SmartTable` with schema-driven filters.
- Public API exposes `/catalog`, `/catalog/random`, and `/catalog/{id}`.
- Tables are created with `Base.metadata.create_all()`.
- There is no Alembic migration system.

This works for a minimal catalog, but product structure is hardcoded. A furniture
shop, clothing shop, food shop, and electronics shop need different product
fields and different navigation.

---

## Target Model

### Categories

Categories are hierarchical.

Rules:

- A category may have one parent.
- A category may have many children.
- A product may be assigned only to a leaf category.
- Non-leaf categories are grouping nodes.
- Category slugs must be unique.
- Active public category trees include only active categories.
- Admin UI should still show inactive categories.

Recommended fields:

| Field | Type | Notes |
|-------|------|-------|
| `id` | integer | Primary key |
| `parent_id` | integer nullable | Self-referencing FK |
| `title` | string | Display name |
| `slug` | string | URL/filter identifier |
| `description` | text | Optional category copy |
| `sort_order` | integer | Sibling ordering |
| `is_active` | boolean | Public visibility |
| `created_at` | datetime | Audit field |

### Tags

Tags are independent from the category tree.

Use tags for labels such as:

- New
- Sale
- Featured
- Gift
- Premium
- For kids

Rules:

- A product may have many tags.
- Tags may be used for public filters.
- Tags may have colors for the admin UI and storefront.
- Tags should not define attributes.

Recommended fields:

| Field | Type | Notes |
|-------|------|-------|
| `id` | integer | Primary key |
| `title` | string | Display name |
| `slug` | string | URL/filter identifier |
| `color` | string | CSS color value |
| `sort_order` | integer | Admin ordering |
| `is_active` | boolean | Public visibility |
| `created_at` | datetime | Audit field |

### Category Attributes

Attributes define category-specific product fields.

Rules:

- Attributes are attached to categories.
- Child categories inherit attributes from all parent categories.
- A child category may add more attributes.
- Attribute `code` must be unique within the inherited category chain.
- Required attributes must be filled before saving a product.
- Filterable attributes appear in product search schema.

Supported first-release types:

| Type | Input | Storage |
|------|-------|---------|
| `text` | text input | `value_text` |
| `number` | number input | `value_number` |
| `boolean` | checkbox | `value_bool` |
| `select` | select | option id or option code |
| `multiselect` | multi-select | JSON array |
| `date` | date input | ISO date string or date column |
| `url` | URL input | `value_text` |
| `color` | color input | `value_text` |
| `file` | file upload/path | `value_text` |
| `image` | image upload/path | `value_text` |

Recommended fields:

| Field | Type | Notes |
|-------|------|-------|
| `id` | integer | Primary key |
| `category_id` | integer | Owning category |
| `code` | string | Stable machine key, for example `size` |
| `title` | string | Admin/storefront label |
| `type` | string | One of the supported types |
| `unit` | string nullable | For number attributes |
| `is_required` | boolean | Product validation |
| `is_filterable` | boolean | Search schema visibility |
| `is_public` | boolean | Product detail visibility |
| `sort_order` | integer | Form display order |

### Attribute Options

`select` and `multiselect` attributes need options.

Recommended fields:

| Field | Type | Notes |
|-------|------|-------|
| `id` | integer | Primary key |
| `attribute_id` | integer | Parent attribute |
| `value` | string | Stable value, for example `red` |
| `label` | string | Display label |
| `sort_order` | integer | Option ordering |

### Product Classification

Products gain:

- `category_id`
- many-to-many tags
- typed attribute values

Rules:

- `category_id` is required after migration.
- `category_id` must point to a leaf category.
- Product attribute values must match the effective attributes of its category.
- Changing a product category should recalculate the form schema.
- Values for attributes no longer valid for the selected category should be
  removed on save in the first release.

---

## Admin UX

### Sidebar

Replace the single catalog entry with a richer catalog group:

```text
Catalog
- Products
- Categories
- Tags
```

The existing products page remains the general product list.

### Categories Page

Route:

```text
GET /admin/categories/
```

Layout:

```text
┌──────────────────────────────┬─────────────────────────────────────────┐
│ Category tree                │ Selected category editor                │
│                              │                                         │
│ Catalog                      │ [Settings] [Attributes] [Products]      │
│ ├ Clothing        24 items   │                                         │
│ │ ├ Women          18 items  │ Settings:                               │
│ │ │ ├ Dresses      12 items  │ - title                                 │
│ │ │ └ Skirts        6 items  │ - slug                                  │
│ │ └ Men             6 items  │ - parent                                │
│ └ Shoes            10 items  │ - active                                │
│                              │ - sort order                            │
└──────────────────────────────┴─────────────────────────────────────────┘
```

Left tree:

- Shows nested categories.
- Shows product counts.
- Highlights the selected category.
- Marks inactive categories visually.
- Provides quick actions: add child, edit, move up, move down.

Right panel tabs:

- `Settings`: category fields and parent selection.
- `Attributes`: inherited attributes and category-owned attributes.
- `Products`: products in selected category.

### Category Settings Tab

Fields:

- `Title`
- `Slug`
- `Description`
- `Parent category`
- `Active`
- `Sort order`

Actions:

- Save category.
- Add child category.
- Deactivate category.
- Delete category if allowed.

Deletion rules:

- Do not delete a category with children.
- Do not delete a category with products.
- In the first release, use explicit deactivate instead of forced cascade.

### Category Attributes Tab

The tab shows two sections:

```text
Inherited from Clothing
- size: select, required, filterable
- color: color, required, filterable
- material: text, optional

Own attributes for Dresses
- length: select, optional, filterable
- season: multiselect, optional, filterable
```

Attribute editor fields:

- `Title`
- `Code`
- `Type`
- `Required`
- `Filterable`
- `Public`
- `Unit`, only for `number`
- Options, only for `select` and `multiselect`

The UI should prevent adding an attribute whose `code` already exists in the
inherited chain.

### Category Products Tab

This is the key workflow for managing many products by category.

Controls:

- Toggle: `Only this category` / `Include subcategories`.
- Button: `New product in this category`.
- Optional v1 batch action: move selected products to another leaf category.

Table:

- Reuse `SmartTable`.
- Preload category filter state from the selected tree node.
- Show category, tags, price, created date, and actions.

Behavior:

- Selecting a category reloads the products tab.
- For non-leaf categories, default to `Include subcategories`.
- For leaf categories, default to `Only this category`.

### Tags Page

Route:

```text
GET /admin/tags/
```

Use `SmartTable`.

Columns:

- `ID`
- `Title`
- `Slug`
- `Color`
- `Products`
- `Active`
- `Actions`

Form fields:

- `Title`
- `Slug`
- `Color`
- `Active`

### Product Form

Add a `Classification` section:

```text
Category *
[Tree select]

Tags
[New] [Sale] [Featured] [+]

Attributes
Size *
Color *
Material
Length
Season
```

Behavior:

- Selecting a category loads its effective attributes.
- Required fields are marked and validated.
- Select and multiselect fields load options from the attribute definition.
- Changing the category shows a warning because the attribute set may change.
- Saving after category change removes values that are not valid for the new
  category.

---

## Data Model

Planned tables:

```text
categories
tags
product_tags
category_attributes
attribute_options
product_attribute_values
products.category_id
```

Relationship diagram:

```text
categories 1 ──── N categories
    │
    ├── 1 ──── N category_attributes
    │              │
    │              └── 1 ──── N attribute_options
    │
    └── 1 ──── N products

products N ──── N tags
products 1 ──── N product_attribute_values
category_attributes 1 ──── N product_attribute_values
```

`product_attribute_values` should support typed storage:

| Field | Purpose |
|-------|---------|
| `product_id` | Product FK |
| `attribute_id` | Attribute definition FK |
| `value_text` | Text, URL, color, file path, image path, select value |
| `value_number` | Numeric value |
| `value_bool` | Boolean value |
| `value_json` | Multiselect or fallback structured value |

This avoids forcing all search and sorting through string comparisons.

---

## API Plan

### Public API

#### `GET /catalog/categories/tree`

Returns active categories as a nested tree.

Use cases:

- Storefront navigation.
- Category menu.
- Breadcrumb construction.

#### `GET /catalog/tags`

Returns active tags.

Use cases:

- Storefront tag filters.
- Marketing labels.

#### `GET /catalog`

Extend the existing endpoint.

New query params:

| Param | Example | Meaning |
|-------|---------|---------|
| `category` | `dresses` | Category slug |
| `category_id` | `12` | Category id |
| `include_descendants` | `true` | Include child categories |
| `tags` | `sale,new` | Tag slug list |
| `attr.size` | `m` | Attribute equality |
| `attr.price_power__gte` | `100` | Attribute operator |

Existing params remain:

- `page`
- `limit`

#### `GET /catalog/{product_id}`

Extend product detail with:

- category summary
- category path
- tags
- public attributes

### Admin API

#### Categories

```text
GET    /catalog/admin/categories/tree
GET    /catalog/admin/categories/{id}
POST   /catalog/admin/categories
PUT    /catalog/admin/categories/{id}
DELETE /catalog/admin/categories/{id}
POST   /catalog/admin/categories/{id}/move
GET    /catalog/admin/categories/{id}/products
```

#### Category attributes

```text
GET    /catalog/admin/categories/{id}/attributes
POST   /catalog/admin/categories/{id}/attributes
PUT    /catalog/admin/categories/{id}/attributes/{attribute_id}
DELETE /catalog/admin/categories/{id}/attributes/{attribute_id}
```

The `GET` endpoint should return both inherited and own attributes.

#### Tags

```text
GET    /catalog/admin/tags
GET    /catalog/admin/tags/search/schema
POST   /catalog/admin/tags
PUT    /catalog/admin/tags/{id}
DELETE /catalog/admin/tags/{id}
```

#### Product search schema

Extend:

```text
GET /catalog/admin/search/schema
```

Add fields:

- category
- tags
- filterable attributes for the selected category when category context is
  provided
- generic category/tag fields when no category context is provided

---

## Filtering And Search

The current `SqlBaseRepo._apply_filters()` works for direct model columns only.
Category, tag, and attribute filters need explicit handling in `SqlProductRepo`.

Plan:

- Keep direct column filters in `SqlBaseRepo`.
- In `SqlProductRepo.search()`, split filters into direct filters and relation
  filters.
- Direct filters use the existing base implementation.
- Category filters join or compare `ProductModel.category_id`.
- Descendant filters compute descendant category ids first, then apply `IN`.
- Tag filters join through `product_tags`.
- Attribute filters join `product_attribute_values` and compare typed value
  columns based on attribute type.

Filter query examples:

```text
/catalog/admin/search?category_id=12
/catalog/admin/search?category_id=3&include_descendants=true
/catalog/admin/search?tags=sale,new
/catalog/admin/search?attr.size=m
/catalog/admin/search?attr.weight__gte=10
```

For v1, sorting by relation fields can be limited:

- direct product columns: supported
- category title: optional
- tag count or attribute values: not required

---

## Migration And Backfill

The project currently has no Alembic migration system. Tables are auto-created
with `Base.metadata.create_all()`, but `create_all()` does not alter existing
tables.

Add an idempotent script:

```text
data/migrate_taxonomy.py
```

Responsibilities:

- Create missing taxonomy tables.
- Add `products.category_id` if missing.
- Create a default category:

```text
Catalog
└── Uncategorized
```

- Assign existing products to `Uncategorized`.
- Add indexes for common filters.
- Be safe to run multiple times.

Recommended run command:

```bash
PYTHONPATH=src uv run data/migrate_taxonomy.py
```

The application can keep `create_all()` for fresh databases, but existing
deployments need this script once.

---

## Implementation Phases

### Phase 1: Domain and DB

- Add category, tag, attribute, and attribute value domain classes.
- Add domain errors for invalid tree operations, invalid category assignment,
  invalid attribute values, and duplicate attribute codes.
- Add SQLAlchemy models and relationships.
- Add migration/backfill script.

### Phase 2: Repositories and Use Cases

- Add repository interfaces for taxonomy operations.
- Add SQL repositories for categories, tags, and product classification.
- Extend product repository mapping.
- Add use cases:
  - manage categories
  - manage tags
  - manage category attributes
  - assign product classification
  - get effective category attributes
  - search products with taxonomy filters

### Phase 3: Facade and Schemas

- Extend `CatalogFacade`.
- Add Pydantic schemas for tree nodes, tags, attributes, options, and product
  classification.
- Keep facades returning schemas, not domain objects.

### Phase 4: API

- Add public category tree and tags endpoints.
- Extend public catalog filtering.
- Add admin category, tag, and attribute endpoints.
- Extend product create/update endpoints.

### Phase 5: Admin UI

- Add sidebar links.
- Add `/admin/categories/` page.
- Add `/admin/tags/` page.
- Add taxonomy JS components:
  - `taxonomy-tree.js`
  - `tag-picker.js`
  - `attribute-form.js`
- Extend product form and product table.

### Phase 6: Demo Data and Docs

- Add superadmin-only demo-data generation for category trees, tags, attributes, and leaf-category products.
- Keep demo generation idempotent; CLI seed files are no longer used.
- Update:
  - `README.md`
  - `docs/database.md`
  - `docs/api_public.md`
  - `docs/api_admin.md`
  - `docs/filters.md`
  - `docs/adding_new_table.md`

---

## Test Plan

There is no current project test suite, so add a small focused test foundation.

### Domain tests

- Category can be nested.
- Product cannot be assigned to non-leaf category.
- Attribute inheritance returns parent attributes before child attributes.
- Duplicate attribute code in inherited chain is rejected.
- Required attribute validation fails when missing.
- Attribute type validation rejects invalid values.

### Repository tests

Use a temporary SQLite database.

- Create category tree.
- Create tags.
- Assign product to leaf category.
- Assign product tags.
- Save and load attribute values.
- Search products by category.
- Search products by category including descendants.
- Search products by tag.
- Search products by number/text/select attributes.

### API tests

Use Flask test client.

- `GET /catalog/categories/tree`
- `GET /catalog/tags`
- `GET /catalog?category=...`
- `GET /catalog?tags=...`
- Admin category CRUD.
- Admin tag CRUD.
- Admin attribute CRUD.
- Product create/update with category, tags, and attributes.
- Invalid category assignment returns 422.
- Invalid attribute value returns 422.

### UI smoke checks

- Open `/admin/categories/`.
- Create root category.
- Create child category.
- Add attributes to parent and child.
- Open `/admin/products/new?category_id=...`.
- Confirm inherited attributes render.
- Save product.
- Return to category products tab and see the product.
- Filter products by category, tag, and attribute.

### Migration checks

- Start from an existing DB with only products.
- Run `data/migrate_taxonomy.py`.
- Confirm taxonomy tables exist.
- Confirm `Uncategorized` category exists.
- Confirm old products have `category_id`.
- Confirm `/catalog` still works.

---

## Open Decisions

These decisions can be deferred without blocking v1:

- Whether to add drag-and-drop category tree reordering.
- Whether batch product movement between categories is required in v1.
- Whether to introduce global attribute templates outside specific categories.
- Whether storefront URLs should use only category slug or full category path.
- Whether inactive parent categories should hide all active children publicly.

Recommended defaults for v1:

- No drag-and-drop. Use parent selector and order buttons.
- Batch movement can be added after core taxonomy is stable.
- Attributes live on categories only.
- Public filters accept category id and category slug.
- Inactive parent hides its subtree publicly.
