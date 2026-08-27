# QR generation

Code: `app/services/payloads.py` (what to encode) and `app/services/qr_service.py`
(how to render it).

## QR code basics

A QR code is a 2-D grid of black/white "modules". It contains:

- **Finder patterns** — the three big squares in the corners a scanner uses to
  locate and orient the code.
- **Timing/alignment patterns** — help the scanner map the grid.
- **Data + error-correction codewords** — the actual payload plus redundancy.
- **Quiet zone** — a blank margin (≥ 4 modules) around the code. Without it,
  scanners often fail to detect the code against a busy background.

The **version** (1–40) determines the grid size; higher versions hold more data.
The library picks the smallest version that fits your payload at the chosen error
level.

## Payloads: encoding each content type

`build_payload(qr_type, content)` produces the exact text encoded into a static
QR. Each type uses the standard format phone cameras recognise:

| Type | Encoded text | Effect when scanned |
|------|--------------|---------------------|
| url | `https://example.com` | opens the link |
| text | the raw text | shows the text |
| wifi | `WIFI:T:WPA;S:ssid;P:pass;;` | offers to join the network |
| vcard | a `BEGIN:VCARD … END:VCARD` block | offers to add the contact |
| email | `mailto:to?subject=…&body=…` | opens a pre-filled email |
| phone | `tel:+15551234567` | starts a call |

Reserved characters are escaped where the format requires it (e.g. `\`, `;`, `,`,
`:` in the Wi-Fi format; commas/semicolons in vCard values), so a password
containing a `;` doesn't break the payload.

## Error correction

QR codes use Reed–Solomon error correction with four levels:

| Level | Recoverable | Use |
|-------|-------------|-----|
| L | ~7% | maximum data, clean conditions |
| M | ~15% | **default** — good balance |
| Q | ~25% | some damage expected |
| H | ~30% | best; required when adding a logo |

Higher levels add redundancy (a larger/denser code) but let the scanner recover
if part of the code is damaged or covered.

## Library choice: segno

We use **segno** rather than the more common `qrcode` library because segno
renders **true vector SVG** and can produce the module matrix we draw into a
vector **PDF**. `qrcode` is raster-first (it goes through Pillow). For raster PNG
output and logo compositing we render segno to PNG and use Pillow.

## Logo embedding (why big logos break codes)

A logo covers data modules. Error correction can rebuild covered modules only up
to its limit, so a logo that's too large makes the code unrecoverable. Our
pipeline (`_embed_logo` in `qr_service.py`):

1. **Validate** the upload (size cap, real image, allowed format, sane dimensions).
2. **Force error level H** whenever a logo is present.
3. **Resize** the logo to at most ~22% of the QR width.
4. **Paint a background patch** behind it (in the code's background colour) so the
   logo sits in a clean area rather than on top of data.
5. **Composite** the logo in the centre.

The result still decodes — `tests/test_qr_decode.py::test_logo_qr_still_decodes`
proves a logo QR round-trips.

## Scannability warnings

`scannability_warnings()` returns non-fatal warnings shown under the live
preview when a choice may hurt scanning:

- **Low contrast** between foreground and background.
- **Inverted** colours (light foreground on dark background) — many scanners
  expect dark-on-light.
- **Quiet zone below 4 modules.**
- An **info** note that error correction was raised to H for a logo.

We surface these rather than silently producing a pretty-but-unscannable code.

## Verification (decode-back)

`decode_png()` decodes a rendered QR with OpenCV, and `verify_png()` checks it
equals the expected text. This is exposed at `GET /api/qr/{id}/verify` (the UI
shows a "verified scannable" badge from a real decode) and is exercised across
all content types in the test suite. OpenCV's decoder is self-contained (no
system `zbar` dependency), which keeps the Docker image simple. It is a strong
signal, not a guarantee for every physical camera — see
[limitations.md](limitations.md).
