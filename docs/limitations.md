# Limitations

Stated plainly, because hiding them is worse than having them.

## QR scanning
- No system guarantees a generated QR scans in every physical condition (print
  quality, lighting, camera, angle, damage). Decode-verification runs in tests
  and via `/api/qr/{id}/verify` using OpenCV — a strong signal, **not** a promise
  for every real-world camera.
- Heavy customisation (low contrast, inverted colours, large logo) can make a
  code hard or impossible to scan. We warn about these but don't forbid them.

## Analytics
- **Location is approximate** and only recorded when available; it is coarse
  (country/region), never precise.
- **User-agent detection is imperfect.** Spoofed, unusual, or new UA strings may
  be miscategorised or fall into "unknown".
- **Counts can be inflated** by bots, link prefetchers, and repeat scans. Obvious
  bots are categorised, but there is no aggressive de-duplication.
- Aggregation is done in Python after a ranged query — fine at this scale, not
  optimal for millions of events.

## Security
- No email verification, password reset, 2FA, or account lockout.
- The JWT lives in `localStorage`; an XSS bug on the page could read it. A fuller
  design would use httpOnly cookies + CSRF protection.
- We block dangerous URL **schemes** and allow deactivating a code, but we do
  **not** scan redirect destinations for phishing/malware. No such protection is
  claimed.
- Rate limiting is basic and per-process (in-memory), not distributed.
- JWTs can't be revoked before they expire.

## Operational
- SQLite is the default; concurrent write-heavy workloads need PostgreSQL.
- Schema changes rely on `create_all` (no Alembic migrations yet).
- The Docker image build was validated for config only, not built to completion,
  in the environment where this project was assembled.
- The app has not been deployed publicly; no uptime/performance numbers are
  claimed ("not evaluated").

## Testing
- No load/performance tests and no automated browser end-to-end tests; the UI is
  verified manually and via screenshots.
