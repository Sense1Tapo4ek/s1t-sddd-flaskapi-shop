# Subsystem: smart filters & SmartTable

For contributors adding a searchable admin list or extending an
existing one. End-to-end coverage: backend filter schema, query param
convention, frontend table component.

## Mental model

```
┌──────────────┐  GET /search/schema   ┌────────────┐
│  SmartTable  │ ──────────────────────│  Flask API │
│  (frontend)  │  GET /search?filters  │            │
│              │ ──────────────────────│            │
└──────────────┘                       └────────────┘
```

1. SmartTable fetches the filter schema on first load.
2. Renders "+" filter buttons per column based on the schema.
3. User picks field + operator + value → URL query is built.
4. Search endpoint applies filters to the SQL query.

## Backend schema format

`GET /<entity>/search/schema` returns:

```json
{
  "fields": [
    { "key": "id",    "label": "ID",   "type": "number", "operators": ["eq"] },
    { "key": "title", "label": "Имя",  "type": "string", "operators": ["ilike", "eq"] },
    { "key": "price", "label": "Цена", "type": "number", "operators": ["eq", "gte", "lte"] },
    {
      "key": "status", "label": "Статус", "type": "enum", "operators": ["eq"],
      "options": [
        { "value": "new", "label": "Новый" },
        { "value": "done", "label": "Выполнен" }
      ]
    }
  ]
}
```

Field properties:

| Property | Required | Notes |
|---|---|---|
| `key` | yes | Column name in the DB / key in response items |
| `label` | yes | Human-readable label shown in filter UI |
| `type` | yes | `string`, `number`, `date`, or `enum` |
| `operators` | yes | Subset of supported operators |
| `options` | enum only | `[{value, label}]` pairs |

Supported operators:

| Operator | Meaning | SQL | UI label |
|---|---|---|---|
| `eq` | Equals | `column = value` | `=` |
| `ilike` | Contains (case-insensitive) | `column ILIKE %val%` | `содержит` |
| `gte` | Greater or equal | `column >= value` | `≥` |
| `lte` | Less or equal | `column <= value` | `≤` |

## Query param convention

```
field__operator=value
```

`__eq` is omitted: `status=new` is equivalent to `status__eq=new`.

Examples:

```
GET /catalog/admin/search?title__ilike=phone&price__gte=100&price__lte=500
GET /inquiries?status=new&name__ilike=alice&created_at__gte=2025-01-01
GET /orders?status=confirmed&customer_user_id__eq=42
```

### Catalog taxonomy filters

Product search supports relation filters beyond plain columns:

| Query param | Example | Meaning |
|---|---|---|
| `category_id` | `category_id=4` | Products in category id 4 |
| `category` | `category=dresses` | Products in category by slug |
| `include_descendants` | `true` | Include child categories |
| `tags` | `sale,new` | Products with ANY listed tag slug |
| `attr.<code>` | `attr.size=M` | Attribute equality |
| `attr.<code>__gte` | `attr.weight__gte=10` | Numeric attribute bound |

## Existing endpoints

| Entity | Schema | Search |
|---|---|---|
| Products | `GET /catalog/admin/search/schema` | `GET /catalog/admin/search` |
| Inquiries | `GET /inquiries/search/schema` | `GET /inquiries` |
| Orders | `GET /orders/search/schema` | `GET /orders` |
| Tags | `GET /catalog/admin/tags/search/schema` | `GET /catalog/admin/tags` |

All require JWT.

## Frontend: SmartTable

`static/js/smart-table.js` exposes the `SmartTable` class:

```javascript
window.productsTable = new SmartTable({
  instanceName: 'productsTable',
  endpoint: '/catalog/admin/search',
  schemaEndpoint: '/catalog/admin/search/schema',
  containerId: 'products-container',
  defaultSortBy: 'created_at',
  defaultSortDir: 'desc',
  columns: [
    { key: 'id',    label: '#',     sortable: true },
    { key: 'title', label: 'Name',  sortable: true },
    { key: 'price', label: 'Price', sortable: true,
      render: p => p.price + ' BYN' },
  ],
});
window.productsTable.load();
```

Column properties: `key`, `label`, `sortable` (bool), `visible` (bool,
default true), `render` (optional `(item) => htmlString`).

Built-in features:

- Filter chips with operator/value popover.
- Column visibility toggle.
- Pagination with page-size selector (10/20/50).
- Sortable headers with direction indicator.

## Adding filters for a new entity

1. **Schema endpoint** in `src/<context>/adapters/driving/api.py`:

   ```python
   @bp.get("/search/schema")
   @jwt_required
   @bp.doc(summary="Filter schema (ADMIN ONLY)", security="JWTAuth")
   @inject
   def search_schema(facade: FromDishka[YourFacade]):
       return {"fields": [...]}
   ```

2. **Search endpoint** that strips reserved params and passes the rest
   to the facade:

   ```python
   reserved = {"page", "limit", "sort_by", "sort_dir"}
   filters = {k: v for k, v in request.args.items()
              if k not in reserved and v != ""}
   return facade.search(filters=filters, **query.model_dump()).model_dump()
   ```

3. **Repository** translates `field__op=value` pairs to SQL through a
   whitelist. Never forward unknown keys to the ORM filter helper —
   that is how public/admin boundary leaks happen.

4. **Admin template** instantiates `SmartTable` with the matching
   `endpoint` and `schemaEndpoint`.

## Performance notes

- Both the items query AND the count query run for every page load.
  Check both when adding joins.
- Cap `limit`; validate `page >= 1`.
- Use `selectinload(...)` for images/tags/category/attributes to avoid
  N+1.

## Pointers

- Frontend class: `static/js/smart-table.js`
- Repository filter handling: `src/catalog/ports/driven/sql_product_repo.py`,
  `src/ordering/ports/driven/sql_order_repo.py`
- Admin contract: [../contract/admin.md](../contract/admin.md)
