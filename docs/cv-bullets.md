# CV bullet points

Three truthful versions — pick the one that matches the role. None invent metrics;
each describes what the code actually does.

## Technical (full-stack)
- Built a full-stack QR management platform (FastAPI, SQLAlchemy, vanilla JS) supporting static and dynamic QR codes, with a documented REST API and OpenAPI docs.
- Implemented dynamic QR redirects using unguessable short IDs, letting a printed code's destination change without reprinting, with server-side scan tracking.
- Added JWT authentication, bcrypt password hashing, and server-side ownership checks; wrote 56 pytest tests including QR decode-verification and authorization cases.
- Containerised the app with Docker and a docker-compose PostgreSQL profile; configuration via environment variables.

## Backend-focused
- Designed a REST API in FastAPI with a clean service layer, Pydantic validation, dependency-injected auth, and consistent HTTP status/error handling.
- Modelled a normalized schema (users, QR projects, scan events) in SQLAlchemy with appropriate indexes and cascade deletes; SQLite in dev, PostgreSQL-ready.
- Enforced authorization server-side (IDOR-safe 404s) and validated redirect URLs against an http/https allow-list, re-checked on every scan.
- Built privacy-conscious analytics that store a salted IP hash and coarse device/browser data — never raw IP addresses.

## Product-focused
- Shipped a QR generator/manager for links, Wi-Fi, contacts, email and phone, with colour/logo customisation and PNG, SVG and PDF export.
- Differentiated static vs dynamic codes and let users edit a live code's destination and view scan analytics through a clean, responsive dashboard.
- Added readability safeguards (contrast and quiet-zone warnings, plus decode-verification) so generated codes are actually scannable.
- Documented the system end-to-end (architecture, security, privacy, limitations) for maintainability.
