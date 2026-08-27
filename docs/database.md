# Database design

Three tables, defined in `app/db/models.py`.

## Tables

### `users`
| column | type | notes |
|--------|------|-------|
| id | int PK | |
| email | string, **unique, indexed** | login lookup |
| password_hash | string | bcrypt hash, never plaintext |
| display_name | string | |
| created_at | datetime | |

### `qr_projects`
| column | type | notes |
|--------|------|-------|
| id | int PK | internal id (never exposed in public URLs) |
| short_id | string, **unique, indexed** | random id used in `/r/<short_id>` |
| owner_id | int FK → users.id, **indexed** | ownership + listing |
| name | string | |
| qr_type | string | url / text / wifi / vcard / email / phone |
| mode | string | static / dynamic |
| content | JSON | payload fields for the type |
| destination_url | text (nullable) | editable target for dynamic codes |
| style | JSON | colours, scale, border, error level |
| logo_data | text (nullable) | base64 PNG of the uploaded logo |
| active | bool | inactive codes stop redirecting |
| created_at / updated_at | datetime | |

### `scan_events`
| column | type | notes |
|--------|------|-------|
| id | int PK | |
| qr_id | int FK → qr_projects.id, **indexed** | aggregation |
| timestamp | datetime, **indexed** | time-series |
| device_type | string | mobile/tablet/desktop/bot/unknown |
| browser | string | family only |
| operating_system | string | family only |
| country | string (nullable) | coarse region |
| referrer | string (nullable) | |
| ip_hash | string (nullable) | salted sha256, truncated — **not** a raw IP |
| is_demo | bool | true for synthetic seed rows |

## Relationships

- `User 1—* QRProject` (a user owns many projects)
- `QRProject 1—* ScanEvent` (a dynamic code accumulates many scans)

Both relationships cascade on delete: deleting a user deletes their projects,
and deleting a project deletes its scan events. This keeps orphaned analytics
from lingering.

## Design decisions

- **JSON columns for `content` and `style`.** Different QR types need different
  fields (a URL needs one, a vCard six). A JSON blob avoids a wide table full of
  mostly-NULL columns. The trade-off — you can't filter inside the JSON in SQL —
  is fine because we never need to.
- **`short_id` is not the primary key.** Public redirect URLs use a random
  `short_id`, not the sequential `id`, so codes can't be enumerated by counting
  up (`/r/1`, `/r/2`, …). See [security.md](security.md#id-enumeration).
- **Indexes are placed on what we actually query:** `email` (login),
  `short_id` (every redirect), `owner_id` (listing a user's codes), and
  `scan_events.qr_id` + `timestamp` (analytics).
- **No `GeneratedAsset` table.** QR images are cheap to regenerate from the
  stored payload + style, so caching them in the DB would add complexity with no
  measured benefit. (Noted as a possible future optimisation, not a current need.)

## Migrations

The app calls `Base.metadata.create_all()` on startup, which creates any missing
tables. That's enough here. A production system with an evolving schema would use
Alembic migrations instead — listed in [future-improvements.md](future-improvements.md).
