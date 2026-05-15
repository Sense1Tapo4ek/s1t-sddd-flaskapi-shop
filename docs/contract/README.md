# API Contract

Wire-level reference for clients that call this service over HTTP. The
pages in this folder are the source of truth for consumers — they
should NEVER need to read context references or Python code to call
the API correctly.

## Layout

| Page | Audience | Content |
|---|---|---|
| [common.md](common.md) | every consumer | Auth, CSRF, error model, error codes |
| [public.md](public.md) | storefront / unauthenticated clients | `/catalog`, `/orders`, `/system/info`, recovery |
| [admin.md](admin.md) | admin UI + external admin clients | `/auth`, admin catalog, taxonomy, orders, settings |

## Base URL

`http://localhost:5000` in dev. Production URL is the deployed
domain.

## Versioning

The API does not carry a path version yet. Breaking changes bump the
shop template release version; consumers should pin a release tag.

## Transport rules

- JSON request/response by default; content type `application/json;
  charset=utf-8`.
- File uploads use `multipart/form-data` (product create/update).
- Successful responses are 2xx; failures use semantic HTTP status codes
  (see [common.md](common.md)).

## OpenAPI

Swagger UI is available at `/api/docs` when `ROOT_APP_ENV=dev`. It is
disabled in production. Admin HTMX pages are not part of OpenAPI.

## Pointers

- Auth/permissions subsystem: [../subsystems/auth-permissions.md](../subsystems/auth-permissions.md)
- Smart filters: [../subsystems/smart-filters.md](../subsystems/smart-filters.md)
- Architecture: [../architecture.md](../architecture.md)
