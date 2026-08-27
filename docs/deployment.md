# Deployment

## Configuration

All configuration is environment-based (`app/core/config.py`, read from `.env`):

| Variable | Meaning |
|----------|---------|
| `ENVIRONMENT` | `development` or `production` |
| `SECRET_KEY` | JWT signing secret — long & random in prod |
| `BASE_URL` | public URL; **baked into every dynamic QR** as `<BASE_URL>/r/<id>` |
| `DATABASE_URL` | `sqlite:///./qr_app.db` or `postgresql+psycopg://…` |

> Set `BASE_URL` to your real domain **before** generating dynamic codes you
> intend to print — the domain is part of the encoded image and can't change
> afterward without reprinting.

## Local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # set a real SECRET_KEY
python -m scripts.seed_data   # optional demo data
uvicorn app.main:app --reload
```

## Docker

```bash
docker compose up --build                        # SQLite
docker compose --profile postgres up --build     # with PostgreSQL
```

For the Postgres profile, set in `.env`:
```
DATABASE_URL=postgresql+psycopg://qr:qr@db:5432/qrdb
```

> The Dockerfile and compose file are written and `docker compose config`
> validates, but the image build was not run to completion in the environment
> where this project was assembled (the container registry was blocked). Build
> and run it locally to confirm.

## Production notes

- Run behind a reverse proxy (nginx/Caddy) terminating TLS; forward
  `X-Forwarded-For` so rate limiting and IP hashing see the real client.
- Run uvicorn with multiple workers, or under gunicorn with uvicorn workers.
- Use PostgreSQL and add Alembic migrations before schema changes.
- Serve the `frontend/` static files from the proxy/CDN rather than the app.

## Database setup

On first start the app creates its tables automatically
(`Base.metadata.create_all`). No manual migration step is needed for the initial
schema. For SQLite the database is a single file (path from `DATABASE_URL`); for
PostgreSQL, create the database/user first (the compose `db` service does this
for you).

## Honesty

This project has **not** been deployed to a public host as part of its assembly,
so no live URL, uptime, or performance figures are claimed. The steps above are
the standard path; verify them in your own environment.
