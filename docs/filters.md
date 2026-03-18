# Smart Filter System

The project implements a dynamic filter system where each entity exposes its **filter schema** via a dedicated API endpoint. The admin frontend (`SmartTable` JS class) fetches this schema at runtime and renders filter UI automatically.

---

## How It Works

```
┌─────────────┐    GET /search/schema     ┌──────────────┐
│  SmartTable  │ ──────────────────────── │  API endpoint │
│  (frontend)  │                          │  (Flask)      │
│              │    GET /search?filters    │               │
│              │ ──────────────────────── │               │
└─────────────┘                           └──────────────┘
```

1. **Schema endpoint** returns a JSON descriptor of available filter fields
2. **SmartTable** renders filter popover UI based on this schema
3. User picks a field, operator, and value → query param is built
4. **Search endpoint** receives filters as query params and applies them to the SQL query

---

## Schema Format

Each schema endpoint returns:

```json
{
  "fields": [
    {
      "key": "title",
      "label": "Name",
      "type": "string",
      "operators": ["ilike", "eq"]
    },
    {
      "key": "price",
      "label": "Price",
      "type": "number",
      "operators": ["eq", "gte", "lte"]
    },
    {
      "key": "status",
      "label": "Status",
      "type": "enum",
      "operators": ["eq"],
      "options": [
        { "value": "new", "label": "New" },
        { "value": "done", "label": "Done" }
      ]
    }
  ]
}
```

### Field Properties

| Property    | Required | Description                                              |
|-------------|----------|----------------------------------------------------------|
| `key`       | yes      | Column name in the database / field key in API response  |
| `label`     | yes      | Human-readable label shown in the filter UI              |
| `type`      | yes      | One of: `string`, `number`, `date`, `enum`               |
| `operators` | yes      | List of allowed operators for this field                 |
| `options`   | no       | Only for `type: "enum"`. Array of `{value, label}` pairs |

### Supported Operators

| Operator | Meaning             | SQL equivalent       | UI label   |
|----------|---------------------|----------------------|------------|
| `eq`     | Equals              | `column = value`     | `=`        |
| `ilike`  | Contains (case-ins) | `column ILIKE %val%` | `содержит` |
| `gte`    | Greater or equal    | `column >= value`    | `≥`        |
| `lte`    | Less or equal       | `column <= value`    | `≤`        |

---

## Query Param Convention

Filters are sent as query parameters in the format:

```
field__operator=value
```

For the `eq` operator, the `__eq` suffix is omitted:

```
field=value
```

### Examples

```
GET /catalog/admin/search?title__ilike=phone&price__gte=100&price__lte=500
GET /orders?status=new&name__ilike=alice&created_at__gte=2025-01-01
```

---

## Existing Schema Endpoints

| Entity   | Schema URL                       | Search URL                |
|----------|----------------------------------|---------------------------|
| Products | `GET /catalog/admin/search/schema` | `GET /catalog/admin/search` |
| Orders   | `GET /orders/search/schema`       | `GET /orders`              |

Both endpoints require JWT authentication.

---

## Frontend: SmartTable

The `SmartTable` class (`static/js/smart-table.js`) handles everything automatically:

```javascript
window.productsTable = new SmartTable({
  instanceName: 'productsTable',        // global var name for callbacks
  endpoint: '/catalog/admin/search',    // search API
  schemaEndpoint: '/catalog/admin/search/schema',  // filter schema API
  containerId: 'products-container',    // DOM element ID
  defaultSortBy: 'created_at',
  defaultSortDir: 'desc',
  columns: [
    { key: 'id',    label: '#',     sortable: true },
    { key: 'title', label: 'Name',  sortable: true },
    { key: 'price', label: 'Price', sortable: true, render: p => p.price + ' BYN' },
    // custom render functions are optional
  ]
});

window.productsTable.load();
```

### Column Properties

| Property   | Type     | Description                                    |
|------------|----------|------------------------------------------------|
| `key`      | string   | Matches `key` in the API response items        |
| `label`    | string   | Column header text                             |
| `sortable` | boolean  | Whether clicking the header sorts by this key  |
| `visible`  | boolean  | Initial visibility (default: `true`)           |
| `render`   | function | Optional custom render: `(item) => htmlString` |

### Features

- Fetches filter schema on first load → renders "+" filter buttons in column headers
- Filter popover with operator selection and value input
- Active filters shown as removable chips above the table
- Column visibility toggle
- Pagination with page size selector (10 / 20 / 50)
- Sortable columns with direction indicator

---

## Adding Filters for a New Entity

1. **Create the schema endpoint** in `src/{context}/adapters/driving/api.py`:

```python
@your_bp.get("/search/schema")
@jwt_required
@your_bp.doc(
    summary="Filter schema (ADMIN ONLY)",
    description="Returns filter field definitions.",
    security="JWTAuth",
)
@inject
def search_schema(facade: FromDishka[YourFacade]):
    return {
        "fields": [
            {"key": "id", "label": "ID", "type": "number", "operators": ["eq"]},
            {"key": "name", "label": "Name", "type": "string", "operators": ["ilike", "eq"]},
            # ... add fields matching your model columns
        ]
    }
```

2. **Create the search endpoint** that accepts filter query params:

```python
@your_bp.get("/search")
@jwt_required
@your_bp.input(YourSearchQuery, location="query")
@your_bp.doc(summary="Search (ADMIN ONLY)", security="JWTAuth")
@inject
def search(query_data: YourSearchQuery, facade: FromDishka[YourFacade]):
    raw = request.args.to_dict()
    reserved = {"page", "limit", "sort_by", "sort_dir"}
    filters = {k: v for k, v in raw.items() if k not in reserved and v != ""}
    return facade.search(filters=filters, **query_data.model_dump()).model_dump()
```

3. **Wire SmartTable** in the admin template — see [adding_new_table.md](adding_new_table.md), step 10.
