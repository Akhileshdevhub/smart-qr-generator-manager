# REST API

Interactive docs (OpenAPI/Swagger UI) are served at **`/docs`**; the raw schema
is at `/openapi.json`. The docs are generated automatically by FastAPI from the
route signatures and Pydantic schemas.

## Authentication

Register, then log in to receive a JWT. Send it as a header on protected calls:

```
Authorization: Bearer <access_token>
```

In `/docs`, click **Authorize** and paste the token.

## Endpoints

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/api/auth/register` | – | Create an account (201) |
| POST | `/api/auth/login` | – | Get a JWT |
| GET | `/api/auth/me` | ✔ | Current user |
| PUT | `/api/auth/me` | ✔ | Update display name |
| POST | `/api/qr/preview` | – | Render a PNG for options without saving |
| POST | `/api/qr` | ✔ | Create a QR project (201) |
| GET | `/api/qr` | ✔ | List your QR projects |
| GET | `/api/qr/{id}` | ✔ | Get one project |
| PUT | `/api/qr/{id}` | ✔ | Update name / destination / active / style |
| DELETE | `/api/qr/{id}` | ✔ | Delete (204) |
| POST | `/api/qr/{id}/duplicate` | ✔ | Copy to a new code |
| POST | `/api/qr/{id}/logo` | ✔ | Upload a centre logo (multipart) |
| DELETE | `/api/qr/{id}/logo` | ✔ | Remove the logo |
| GET | `/api/qr/{id}/image` | ✔ | Rendered PNG of the saved code |
| GET | `/api/qr/{id}/download?fmt=png\|svg\|pdf` | ✔ | Download a file |
| GET | `/api/qr/{id}/verify` | ✔ | Decode-back check |
| GET | `/api/qr/{id}/analytics` | ✔ | Per-QR analytics |
| GET | `/api/analytics/overview` | ✔ | Account-wide analytics |
| GET | `/r/{short_id}` | – | Public dynamic redirect (302) |

## Status codes used

- `200` success, `201` created, `204` deleted (no body).
- `401` missing/invalid token, `404` not found **or not yours**, `409` conflict
  (duplicate email; unset destination), `410` gone (inactive redirect),
  `422` validation error, `429` rate limited, `500` unexpected (generic message).

## Request/response validation

Every request body is a Pydantic model (`app/schemas/`), so malformed input is
rejected with a `422` describing the problem before any handler runs. Responses
use `response_model=` so the API only ever returns documented fields.

## Example

```bash
# Register + login
curl -s -X POST localhost:8000/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"me@example.com","password":"password123"}'

TOKEN=$(curl -s -X POST localhost:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"me@example.com","password":"password123"}' | jq -r .access_token)

# Create a dynamic QR
curl -s -X POST localhost:8000/api/qr \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"name":"Menu","qr_type":"url","mode":"dynamic","destination_url":"https://example.com/menu"}'

# Download it as a PDF
curl -s "localhost:8000/api/qr/1/download?fmt=pdf" -H "Authorization: Bearer $TOKEN" -o menu.pdf
```
