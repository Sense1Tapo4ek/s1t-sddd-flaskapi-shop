# Adding a New Entity (Table + Schema + Filters + Admin UI)

This guide walks through adding a new entity to the shop template. We'll use a hypothetical **"Review"** entity as an example, added to the existing `catalog` context.

> If you need a whole new bounded context, see the "Adding a new bounded context" section in `CLAUDE.md`.

---

## Checklist

| # | Layer              | What to create / modify                       |
|---|-------------------|-----------------------------------------------|
| 1 | Domain            | Aggregate / entity class                      |
| 2 | ORM               | SQLAlchemy model                              |
| 3 | App interface     | Abstract repository interface (ABC)           |
| 4 | Driven port       | Concrete SQL repository                       |
| 5 | Schemas           | Pydantic DTOs (In / Out / SearchQuery / List) |
| 6 | Use case          | Business logic orchestration                  |
| 7 | Facade            | Add methods to the context Facade             |
| 8 | API blueprint     | REST endpoints + filter schema endpoint       |
| 9 | Admin blueprint   | HTMX routes for the admin panel               |
| 10| Admin template    | HTML page with SmartTable                     |
| 11| Demo data         | Optional: add entity to a demo-data use case  |
| 12| Wiring            | DI provider + blueprint registration          |

---

## Step 1: Domain — Aggregate

```python
# src/catalog/domain/review_agg.py
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Review:
    id: int
    product_id: int
    author: str
    rating: int        # 1-5
    text: str
    created_at: datetime

    @classmethod
    def create(cls, id: int, product_id: int, author: str, rating: int, text: str) -> "Review":
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be 1-5")
        return cls(id=id, product_id=product_id, author=author,
                   rating=rating, text=text, created_at=datetime.utcnow())
```

---

## Step 2: ORM Model

```python
# Add to src/catalog/adapters/driven/db/models.py

class ReviewModel(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False
    )
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
```

The model will be auto-discovered since all `catalog` models are already imported in `api.py`. No extra import needed.

---

## Step 3: Repository Interface

```python
# src/catalog/app/interfaces/i_review_repo.py
from abc import ABC, abstractmethod
from catalog.domain.review_agg import Review
from shared.generics.pagination import PaginatedResult


class IReviewRepo(ABC):
    @abstractmethod
    def get_by_id(self, review_id: int) -> Review | None: ...

    @abstractmethod
    def search(self, page: int, limit: int, sort_by: str,
               sort_dir: str, filters: dict) -> PaginatedResult[Review]: ...

    @abstractmethod
    def save(self, review: Review) -> None: ...

    @abstractmethod
    def delete(self, review_id: int) -> None: ...
```

---

## Step 4: SQL Repository (Driven Port)

```python
# src/catalog/ports/driven/sql_review_repo.py
from dataclasses import dataclass
from catalog.app.interfaces.i_review_repo import IReviewRepo
from catalog.adapters.driven.db.models import ReviewModel
from shared.adapters.driven.db.base.repository import SqlBaseRepo
# ... implement mapping between domain Review <-> ReviewModel
```

---

## Step 5: Pydantic Schemas

```python
# Add to src/catalog/ports/driving/schemas.py

class ReviewSearchQuery(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)
    page: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)
    sort_by: str | None = None
    sort_dir: str = Field("desc", pattern="^(asc|desc)$")


class ReviewOut(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: int
    product_id: int
    author: str
    rating: int
    text: str
    created_at: str


class ReviewListOut(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[ReviewOut]
    total: int
```

---

## Step 6: Use Case

```python
# src/catalog/app/use_cases/manage_reviews_uc.py
from dataclasses import dataclass
from ..interfaces.i_review_repo import IReviewRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class ManageReviewsUseCase:
    _repo: IReviewRepo

    def search(self, page, limit, sort_by, sort_dir, filters):
        return self._repo.search(page, limit, sort_by, sort_dir, filters)

    def delete(self, review_id: int) -> None:
        self._repo.delete(review_id)
```

---

## Step 7: Facade

```python
# Add to src/catalog/ports/driving/facade.py

class CatalogFacade:
    # ... existing methods ...

    def search_reviews(self, **kwargs) -> ReviewListOut:
        result = self._review_uc.search(**kwargs)
        return ReviewListOut.from_domain(result)
```

---

## Step 8: API Blueprint — REST + Filter Schema

```python
# Add to src/catalog/adapters/driving/api.py

@catalog_bp.get("/reviews/search")
@jwt_required
@catalog_bp.input(ReviewSearchQuery, location="query")
@catalog_bp.doc(
    summary="Search reviews (ADMIN ONLY)",
    description="Paginated review list with filters.",
    security="JWTAuth",
)
@inject
def search_reviews(query_data: ReviewSearchQuery, facade: FromDishka[CatalogFacade]):
    raw = request.args.to_dict()
    reserved = {"page", "limit", "sort_by", "sort_dir"}
    filters = {k: v for k, v in raw.items() if k not in reserved and v != ""}
    return facade.search_reviews(
        page=query_data.page, limit=query_data.limit,
        sort_by=query_data.sort_by, sort_dir=query_data.sort_dir,
        filters=filters,
    ).model_dump()


@catalog_bp.get("/reviews/search/schema")
@jwt_required
@catalog_bp.doc(
    summary="Review filter schema (ADMIN ONLY)",
    description="Field definitions for the reviews smart table.",
    security="JWTAuth",
)
@inject
def review_search_schema(facade: FromDishka[CatalogFacade]):
    return {
        "fields": [
            {"key": "id",         "label": "ID",      "type": "number", "operators": ["eq"]},
            {"key": "author",     "label": "Author",   "type": "string", "operators": ["ilike", "eq"]},
            {"key": "rating",     "label": "Rating",   "type": "number", "operators": ["eq", "gte", "lte"]},
            {"key": "created_at", "label": "Date",     "type": "date",   "operators": ["eq", "gte", "lte"]},
        ]
    }
```

---

## Step 9: Admin Blueprint (HTMX)

```python
# Add to src/catalog/adapters/driving/admin.py  (or create a new admin file)

@catalog_admin_bp.route("/reviews")
@jwt_required
@inject
def reviews_page(facade: FromDishka[CatalogFacade]):
    return render_partial_or_full(
        "catalog/partials/reviews_table.html",
        "catalog/pages/reviews.html",
        reviews=facade.search_reviews(page=1, limit=20, sort_by="created_at", sort_dir="desc"),
    )
```

---

## Step 10: Admin Template with SmartTable

```html
<!-- src/catalog/templates/catalog/pages/reviews.html -->
{% extends "base.html" %}
{% set active = "reviews" %}

{% block title %}Reviews — {{ app_name }}{% endblock %}

{% block content %}
<div class="page-header">
  <h2 class="page-title">Reviews</h2>
</div>
<div id="reviews-container"></div>
{% endblock %}

{% block scripts %}
<script src="/static/js/utils.js"></script>
<script src="/static/js/api.js"></script>
<script src="/static/js/smart-table.js"></script>
<script>
window.reviewsTable = new SmartTable({
  instanceName: 'reviewsTable',
  endpoint: '/catalog/reviews/search',
  schemaEndpoint: '/catalog/reviews/search/schema',
  containerId: 'reviews-container',
  defaultSortBy: 'created_at',
  defaultSortDir: 'desc',
  columns: [
    { key: 'id',         label: '#',       sortable: true },
    { key: 'author',     label: 'Author',  sortable: true },
    { key: 'rating',     label: 'Rating',  sortable: true },
    { key: 'text',       label: 'Text',    sortable: false },
    { key: 'created_at', label: 'Date',    sortable: true },
    {
      key: 'actions', label: 'Actions', sortable: false,
      render: item => `<button class="btn btn--sm" onclick="deleteReview(${item.id})">Delete</button>`
    },
  ]
});
window.reviewsTable.load();
</script>
{% endblock %}
```

---

## Step 11: Demo Data

CLI seed files are no longer used. If the entity needs sample data, add an idempotent generator to an application use case and expose it behind a superadmin-only admin action. Keep demo rows identifiable so repeated clicks do not duplicate them.

---

## Step 12: Wiring

1. **DI Provider** — add to `src/catalog/provider.py`:
   ```python
   review_repo = provide(SqlReviewRepo, provides=IReviewRepo)
   manage_reviews_uc = provide(ManageReviewsUseCase)
   ```

2. **Navigation** — add a link in `static/templates/admin/base.html`:
   ```html
   <a href="/admin/reviews" class="nav-link {% if active == 'reviews' %}nav-link--active{% endif %}">
     Reviews
   </a>
   ```

3. **No extra blueprint registration needed** if you added routes to the existing `catalog_admin_bp`.

---

## Summary

For every new table/entity you need:

- **Model** (ORM) → auto-creates table on startup
- **Schema endpoint** → drives the frontend filter UI
- **Search endpoint** → accepts `field__operator=value` query params
- **SmartTable instance** → auto-renders table + filters from the schema
- **Seed config** → generates mock data
