# Future improvements

Realistic next steps, roughly in order of value. None are implemented — they're
here to show the roadmap and to answer "what would you add next?"

## Product
- **QR expiration** and **scheduled redirects** (a code goes live / changes at a
  set time).
- **A/B destination testing** and basic **campaign/UTM tagging**.
- **Team/shared projects** with roles.
- **Branded short domains** / custom domains for the redirect URL.
- Bulk generation and CSV import/export of codes.

## Analytics
- Push time-series aggregation into SQL (`GROUP BY date_trunc(...)`) for scale.
- Unique-visitor estimation and bot filtering.
- Referrer and geo enrichment via a proper GeoIP database (kept coarse for privacy).

## Platform / API
- **API keys** and per-key usage limits for programmatic access.
- **Webhook events** on scan (for integrations).
- Distributed rate limiting (Redis) instead of in-memory.

## Security & accounts
- Email verification, password reset, 2FA.
- Move the session token to httpOnly cookies + CSRF protection.
- Token revocation / refresh tokens.
- Optional destination-reputation checks for abuse detection.

## Engineering
- **Alembic migrations** for schema evolution.
- Automated browser end-to-end tests (Playwright) and a small load test.
- Cache rendered assets only if profiling shows generation is a bottleneck.
- CI pipeline running the test suite on every push.
