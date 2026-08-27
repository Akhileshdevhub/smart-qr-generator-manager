# Architecture

## Overview

The application is a single FastAPI backend that also serves a static
JavaScript frontend. There are three layers:

1. **Frontend** (`frontend/`) — plain HTML/CSS/JS. It talks to the backend over
   the REST API using `fetch`, storing a JWT in `localStorage`. No build step.
2. **API layer** (`app/api/`) — FastAPI routers. Handles HTTP concerns only:
   request parsing, status codes, auth dependencies, and calling services.
3. **Service layer** (`app/services/`) — the actual logic (QR generation,
   redirect resolution, analytics, auth). Services are plain functions that take
   a DB session and arguments, so they can be unit-tested without HTTP.

Underneath sits the **data layer** (`app/db/`): SQLAlchemy models and a session
factory. Configuration and cross-cutting helpers (security, logging, rate limit)
live in `app/core/`.

```
Browser (frontend/*.html + js)
        │  fetch + JWT
        ▼
FastAPI app (app/main.py)
        │
   ┌────┴───────────────┐
   │  API routers       │  app/api/routes/*   (auth, qr, analytics, redirect)
   │  + dependencies    │  auth + ownership checks
   └────┬───────────────┘
        ▼
   Service layer         app/services/*   (qr, export, redirect, analytics, auth)
        ▼
   SQLAlchemy models     app/db/models.py  (User, QRProject, ScanEvent)
        ▼
   SQLite / PostgreSQL
```

## Why this shape

- **Thin routes, fat services.** Routes are a few lines each; the logic lives in
  services. This keeps the interesting code testable and makes the HTTP layer
  easy to skim.
- **One process serves API + frontend.** For a project of this size, a single
  `uvicorn app.main:app` is the whole app. In production you would usually put
  the static files behind a CDN/nginx and run the API separately, but nothing in
  the code assumes they're together beyond a couple of static-file routes.
- **No unnecessary abstractions.** There is no repository pattern, no dependency-
  injection framework beyond FastAPI's own `Depends`, and no message queue. They
  would add indirection without solving a problem this project has.

## Two request flows worth knowing

**Authenticated API request (e.g. create a QR):**

```
Browser → POST /api/qr (Bearer token)
  → get_current_user   (decode JWT, load User, or 401)
  → validate payload   (schemas + payloads.py; 422 on bad input)
  → qr_service         (allocate short_id, build content)
  → DB commit
  → 201 + QROut JSON
```

**Public scan of a dynamic QR (no auth):**

```
Phone → GET /r/<short_id>
  → redirect_service.resolve_project   (404 if missing, 410 if inactive)
  → analytics_service.record_scan      (device/browser/OS + hashed IP)
  → redirect_service.destination_for   (re-validate http/https)
  → 302 Location: <current destination>
```

See [static-vs-dynamic.md](static-vs-dynamic.md) and [analytics.md](analytics.md)
for the details of each.
