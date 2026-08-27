"""Export a QR to the three download formats, honestly:

  * PNG  -> raster image (pixels). Best for screens/social. Logo supported.
  * SVG  -> true vector (segno draws each module as a shape). Scales to any size
            with no blur. Best for print/design tools. Logo embedded as an image.
  * PDF  -> a printable A4 page. The QR is drawn as vector rectangles (not a
            pasted picture) from the module matrix, so it stays crisp at any
            print size, with the project name and an optional destination label.

The distinction PNG=raster vs SVG/PDF=vector is a real one and is explained in
docs/file_generation.md.
"""
import io

from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from app.services import qr_service


def to_png(encoded_text: str, style: dict, logo: Image.Image | None = None) -> bytes:
    return qr_service.render_png(encoded_text, style, logo)


def to_svg(encoded_text: str, style: dict, logo_bytes: bytes | None = None) -> bytes:
    """Render a true-vector SVG. If a logo is supplied it is embedded as a
    centred <image> element (a small raster inside an otherwise-vector file)."""
    has_logo = logo_bytes is not None
    symbol = qr_service.make_symbol(encoded_text, style.get("error", "M"), has_logo)
    scale = style.get("scale", 10)
    border = style.get("border", 4)

    buf = io.BytesIO()
    symbol.save(
        buf, kind="svg", scale=scale, border=border,
        dark=style.get("fg_color", "#000000"),
        light=style.get("bg_color", "#ffffff"),
        xmldecl=True,
    )
    svg = buf.getvalue().decode("utf-8")

    if has_logo:
        # Size in the SVG's own pixel coordinate space, then drop a base64 logo
        # image over the centre (a background rect keeps contrast, mirroring the
        # PNG logo pipeline).
        total = symbol.symbol_size(scale, border)[0]
        box = int(total * qr_service._LOGO_MAX_FRACTION * 1.18)
        pos = (total - box) // 2
        b64 = qr_service.logo_to_base64(logo_bytes)
        overlay = (
            f'<rect x="{pos}" y="{pos}" width="{box}" height="{box}" '
            f'fill="{style.get("bg_color", "#ffffff")}"/>'
            f'<image x="{pos}" y="{pos}" width="{box}" height="{box}" '
            f'preserveAspectRatio="xMidYMid meet" '
            f'xlink:href="data:image/png;base64,{b64}"/>'
        )
        svg = svg.replace("</svg>", overlay + "</svg>")
        if "xmlns:xlink" not in svg:
            svg = svg.replace("<svg ", '<svg xmlns:xlink="http://www.w3.org/1999/xlink" ', 1)

    return svg.encode("utf-8")


def to_pdf(
    encoded_text: str,
    style: dict,
    title: str,
    label: str | None = None,
    logo_bytes: bytes | None = None,
) -> bytes:
    """Draw a clean A4 sheet with the QR as vector rectangles plus a title and
    optional destination label."""
    has_logo = logo_bytes is not None
    symbol = qr_service.make_symbol(encoded_text, style.get("error", "M"), has_logo)
    matrix = [[bool(m) for m in row] for row in symbol.matrix]
    border = style.get("border", 4)
    n = len(matrix)
    total_modules = n + 2 * border

    page_w, page_h = A4
    qr_size = 95 * mm                       # printed QR side
    module = qr_size / total_modules
    origin_x = (page_w - qr_size) / 2
    origin_y = page_h - 60 * mm - qr_size   # leave room for the title

    out = io.BytesIO()
    c = canvas.Canvas(out, pagesize=A4)

    # Title
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(page_w / 2, page_h - 35 * mm, title[:60])

    # Background rectangle behind the whole QR (quiet zone included)
    c.setFillColor(_rl_color(style.get("bg_color", "#ffffff")))
    c.rect(origin_x, origin_y, qr_size, qr_size, stroke=0, fill=1)

    # Dark modules as vector squares. Row 0 of the matrix is the top of the QR,
    # but PDF y grows upward, so we flip the row index.
    c.setFillColor(_rl_color(style.get("fg_color", "#000000")))
    for r, row in enumerate(matrix):
        y = origin_y + (total_modules - border - 1 - r) * module
        for col, is_dark in enumerate(row):
            if is_dark:
                x = origin_x + (border + col) * module
                c.rect(x, y, module, module, stroke=0, fill=1)

    # Optional logo, centred, over a background patch (error level H covers it).
    if has_logo:
        logo_img = qr_service.validate_logo(logo_bytes).convert("RGBA")
        box = qr_size * qr_service._LOGO_MAX_FRACTION
        patch = box * 1.18
        cx, cy = page_w / 2, origin_y + qr_size / 2
        c.setFillColor(_rl_color(style.get("bg_color", "#ffffff")))
        c.rect(cx - patch / 2, cy - patch / 2, patch, patch, stroke=0, fill=1)
        c.drawImage(ImageReader(logo_img), cx - box / 2, cy - box / 2, box, box, mask="auto")

    # Optional destination label under the QR
    if label:
        c.setFont("Helvetica", 11)
        c.setFillColor(_rl_color("#444444"))
        c.drawCentredString(page_w / 2, origin_y - 12 * mm, label[:90])

    # Small footer note
    c.setFont("Helvetica", 8)
    c.setFillColor(_rl_color("#999999"))
    c.drawCentredString(page_w / 2, 15 * mm, "Generated with Smart QR Generator & Manager")

    c.showPage()
    c.save()
    return out.getvalue()


def _rl_color(hex_color: str):
    from reportlab.lib.colors import HexColor
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    return HexColor(int(h, 16))
