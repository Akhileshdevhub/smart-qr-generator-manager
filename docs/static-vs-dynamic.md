# Static vs dynamic QR codes

This is the central idea of the project.

## Static

A static QR encodes the content **directly**. A static URL code literally
contains `https://example.com`. When scanned, the phone reads that text and acts
on it — no server involved.

- ✅ Works forever, offline, with no backend.
- ❌ To change the destination you must generate and re-print a new code.

`encoded_text_for(..., mode="static", ...)` returns `build_payload(type, content)`.

## Dynamic

A dynamic QR encodes a **redirect URL we control**, e.g.
`https://yourapp.com/r/aB3xK9p`. The real destination is stored in the database.
When scanned:

```
Phone → GET /r/aB3xK9p
  → look up the project by short_id
  → record a scan event
  → 302 redirect to the CURRENT destination
```

Because the image only ever contains `/r/aB3xK9p`, you can change where it points
by updating one database row. **The printed code never changes.** This is what
makes dynamic codes useful for posters, packaging, menus, and campaigns.

- ✅ Editable destination; scan analytics; can be deactivated.
- ❌ Requires the server to be up; introduces redirect-abuse considerations
  (see [security.md](security.md)).

`encoded_text_for(..., mode="dynamic", short_id)` returns
`f"{BASE_URL}/r/{short_id}"`.

## The guarantee, in code

Updating a dynamic code's destination changes `destination_url` only — never
`short_id`. The test
`tests/test_redirect.py::test_changing_destination_keeps_short_id_and_image`
asserts exactly this: after changing the destination, the `short_id` (and
therefore the encoded image) is unchanged, and the redirect now points to the new
URL.

There is deliberately **no** API to change a code's `mode` or `short_id` after
creation — the schema (`QRUpdate`) doesn't expose them.

## Constraint: dynamic is URL-only

Dynamic mode only makes sense for URLs (you can't "redirect" a Wi-Fi payload).
The API rejects a dynamic request for any non-URL type with 422, and the UI
disables the other content-type tabs when Dynamic is selected.

## Redirect endpoint details

`app/api/routes/redirect.py` handles `GET /r/{short_id}`:

- Unknown id → **404**.
- Inactive/archived code → **410 Gone** (a deleted or disabled code stops
  redirecting even though the printed image still exists).
- No/invalid destination → **409**.
- Otherwise → record the scan, re-validate the destination is `http(s)`, and
  **302** to it.

Analytics recording is wrapped so that a logging failure never blocks the
redirect the visitor actually wants.
