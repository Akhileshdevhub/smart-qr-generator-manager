# Scan analytics & privacy

Code: `app/services/analytics_service.py`. Analytics apply to **dynamic** codes
only — static codes never touch the server when scanned, so there's nothing to
record.

## What is collected (per scan)

When `/r/<short_id>` is hit, one `ScanEvent` row is written with:

- a **timestamp**,
- a **device category** — mobile / tablet / desktop / bot / unknown,
- the **browser family** and **OS family** (e.g. "Chrome", "iOS"),
- an optional coarse **country/region** (when available),
- a **hashed IP identifier**: `sha256(SECRET_KEY + ip)[:16]`.

Device/browser/OS come from parsing the `User-Agent` header with the
`user-agents` library.

## What is NOT collected

- **No raw IP address.** We store only the salted, truncated hash, which cannot
  be reversed to an address. The salt is the app secret, so the hash can't be
  pre-computed against a table of all IPv4 addresses. `test_ip_is_not_stored_raw`
  asserts the stored value is neither the IP nor reversible.
- No precise location, names, or per-person profile.

## Why this design

The goal is to give a code's owner a useful **aggregate** picture (how many
scans, on what kind of device, roughly where) without profiling individuals. It's
the minimum that answers "is my campaign working?" while staying privacy-conscious.
A short privacy notice is shown in the app at `/privacy`.

## Aggregation

The dashboards read scans and aggregate in Python:

- **Overview** (`dashboard_overview`): totals across all of a user's codes, scans
  today / this week, a zero-filled 14-day time series, and a top-codes list.
- **Per-QR** (`qr_analytics`): the same time series plus device / browser /
  country breakdowns for one code, and a `contains_demo_data` flag.

Time-series bucketing is done in Python after a single ranged query, rather than
with SQL date functions. This keeps the query **database-agnostic** (SQLite in
dev, PostgreSQL in prod use different date functions) and is perfectly fast at
this scale. For very large datasets you'd push aggregation into SQL with proper
`GROUP BY date_trunc(...)` — noted in [future-improvements.md](future-improvements.md).

## Honesty about the numbers

- Every scan created by `scripts/seed_data.py` is flagged `is_demo = True`, and
  the analytics view shows a clear **"synthetic demo scans"** banner when any are
  present. Demo data is never presented as real traffic.
- Real analytics reflect real scans only. No counts are invented anywhere.
- Bots, prefetchers, and repeat scans can inflate counts; we categorise obvious
  bots but do not de-duplicate aggressively. See [limitations.md](limitations.md).
