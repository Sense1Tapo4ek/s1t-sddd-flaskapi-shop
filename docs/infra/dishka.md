# Infra: Dishka (DI container)

For contributors adding a provider or injecting a new dependency.
Vendor docs are authoritative; this page documents project-specific
conventions only.

## Composition root

`src/root/container.py` is the only place that assembles concrete
context providers:

```python
def build_container() -> Container:
    return make_container(
        FlaskProvider(),
        InfraProvider(),
        SystemProvider(),
        CatalogProvider(),
        OrderingProvider(),
        AccessProvider(),
        StorageProvider(),
    )
```

`InfraProvider` (shared) is registered before context providers so DB
session, file storage, and the Telegram client are available to
everyone.

## Provider layout per context

Each context owns `src/<context>/provider.py`:

```python
class CatalogProvider(Provider):
    scope = Scope.APP

    config = provide(CatalogConfig)

    # Driven ports
    repo = provide(SqlProductRepo, provides=IProductRepo)
    ...

    # Use cases
    list_uc = provide(ListProductsUseCase)
    create_uc = provide(CreateProductUseCase)
    ...

    # Driving facade
    facade = provide(CatalogFacade)
```

Rules:

- `provide(Concrete, provides=Interface)` is the ONLY place that maps a
  concrete class to its Protocol/ABC.
- Never import another context's internals from a provider. Use the
  target's `ports/driving/` (its facade) via an ACL when crossing
  contexts.
- One `<Context>Config` per provider, declared with the matching env
  prefix (see `src/<context>/config.py`).

## Injecting into Flask handlers

```python
from dishka.integrations.flask import inject, FromDishka

@bp.post("/")
@bp.input(CreateProductSchema, location="form")
@inject
def create(data: CreateProductSchema,
           facade: FromDishka[CatalogFacade]) -> dict:
    return facade.create_product(data).model_dump()
```

- `@inject` MUST be inner-most (closest to the function definition).
- Resolve facades, not concrete repos. Handlers never see ORM models.
- Use cases are not injected into handlers; the facade aggregates them.

## Scopes

- `Scope.APP` for stateless services (use cases, repos, facades,
  configs).
- `Scope.REQUEST` only when state genuinely depends on the request
  (e.g., a per-request DB session). The SQLAlchemy session in
  `InfraProvider` is request-scoped through Flask integration.

## Pointers

- Composition root: `src/root/container.py`
- Provider examples: `src/catalog/provider.py`, `src/access/provider.py`
- ADR for Dishka choice: [../adr/0005-dishka-for-di.md](../adr/0005-dishka-for-di.md)
