# Testing

Run: `pytest -q` (56 tests).

## Setup

`tests/conftest.py` runs the suite against an **in-memory SQLite** database that
is created fresh for every test and injected via FastAPI's `dependency_overrides`
(replacing `get_db`). Rate limiting is disabled for the test client. Helpers
`auth_headers()` and `make_qr()` cut boilerplate.

## What's covered

| File | Focus |
|------|-------|
| `test_auth.py` | register, duplicate email (409), login, wrong password (401), short password (422), password stored as bcrypt hash |
| `test_authorization.py` | user A cannot read/edit/delete user B's code (404); list is scoped; protected routes need a token; bad token rejected |
| `test_qr_crud.py` | create, get, update name/style, delete (204), duplicate → new short_id |
| `test_qr_decode.py` | **decode-back tests**: every content type + dynamic + logo QR round-trips to the expected payload |
| `test_redirect.py` | 302 to destination; changing destination keeps short_id; inactive → 410; deleted → 404; unknown → 404; scan recorded; dynamic only for URLs |
| `test_analytics.py` | overview counts, device breakdown, IP stored as hash not raw |
| `test_validation.py` | dangerous URL schemes rejected; wifi/vcard required fields; wifi escaping; mailto building; logo validation + upload; oversized logo |
| `test_exports.py` | PNG magic bytes, SVG is vector, PDF header, bad format (422), verify endpoint |

## Notable edge cases (the ones interviewers like)

- **A deleted / inactive dynamic code stops redirecting** even though the printed
  image still exists in the world.
- **Changing a dynamic destination does not change the short_id** (so the printed
  code keeps working).
- **User A cannot reach user B's code by editing the id** — returns 404, which
  also hides whether the id exists.
- **A logo QR still decodes** thanks to forced error-level H.

## What isn't tested

No load/performance tests, no browser end-to-end tests (the frontend is exercised
manually and via the screenshots), and the Docker build is validated only for
config syntax. These are listed honestly in [limitations.md](limitations.md).
