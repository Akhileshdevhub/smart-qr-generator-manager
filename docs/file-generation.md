# File generation (PNG / SVG / PDF)

Code: `app/services/export_service.py`.

## PNG — raster

A grid of pixels. `segno` renders the QR to PNG at the chosen scale (pixels per
module), colours, and quiet zone; if a logo is attached, Pillow composites it in.
Best for screens and social media. Scaling it up in an image editor makes it
blurry (it's a bitmap).

```
segno.make(text, error=...) → PNG bytes → (optional Pillow logo composite)
```

## SVG — true vector

`segno` draws each QR module as a vector shape in an SVG document. Because it's
vector, it scales to any size — a billboard or a business card — with **no
blur**. This is a real vector QR, not a PNG wrapped in an `<svg>` tag; the test
`test_svg_download_is_vector` checks the output contains actual `<path>`/`<rect>`
shapes. If a logo is attached, it's embedded as a centred `<image>` element (a
small raster inside the otherwise-vector file).

## PDF — printable vector page

`reportlab` builds an A4 page and draws the QR as **vector rectangles** straight
from segno's module matrix (not a pasted picture), so it stays crisp at any print
size. The page includes the project name as a title and an optional destination
label. A logo, if present, is drawn centred over a background patch (error level H
keeps it scannable).

```
segno matrix → for each dark module: reportlab.rect(...)  → vector PDF + title/label
```

## Why the distinction matters

| Format | Type | Scales cleanly? | Good for |
|--------|------|-----------------|----------|
| PNG | raster (pixels) | no | web, chat, quick sharing |
| SVG | vector | yes | design tools, large print |
| PDF | vector page | yes | ready-to-print sheet with a label |

All three are generated on demand from the stored payload + style, so there are
no stale cached images to keep in sync when a code's style changes.
