"""Core QR generation: text -> segno symbol -> raster image, plus the logo
pipeline, readability warnings, and decode-based verification.

Library choice: we use `segno`. Compared with the more common `qrcode`
library, segno produces true vector SVG and can export PDF natively, which
matters for the "real vector SVG" export requirement. For raster output and
logo compositing we render segno to PNG and use Pillow.
"""
import base64
import io
import secrets

import cv2
import numpy as np
import segno
from PIL import Image

from app.core.config import settings
from app.services.payloads import PayloadError, build_payload

# Characters for the public short id. No look-alikes (0/O, 1/l) to make ids
# easier to read off a printed page. 7 chars of this alphabet ~ 3.5e12 combos.
_SHORT_ID_ALPHABET = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_SHORT_ID_LEN = 7

# How much of the QR the logo may cover. Above ~25% of the module area the code
# starts failing to scan even at error level H. We cap the logo box side at 22%
# of the image width as a safe default.
_LOGO_MAX_FRACTION = 0.22

_ALLOWED_LOGO_FORMATS = {"PNG", "JPEG", "WEBP"}


def generate_short_id() -> str:
    """A URL-safe, unguessable id for the public redirect path. Uniqueness is
    enforced by a UNIQUE column; the creating service retries on the rare clash."""
    return "".join(secrets.choice(_SHORT_ID_ALPHABET) for _ in range(_SHORT_ID_LEN))


def encoded_text_for(qr_type: str, content: dict, mode: str, short_id: str) -> str:
    """The exact string that goes into the QR image.

    This is the heart of static vs dynamic:
      * static  -> encode the real content (URL, wifi, vCard, ...)
      * dynamic -> encode our redirect endpoint <base_url>/r/<short_id>. The real
        destination is looked up server-side at scan time, so the *image* never
        has to change when the user edits where it points.
    """
    if mode == "dynamic":
        return f"{settings.base_url}/r/{short_id}"
    return build_payload(qr_type, content)


def _effective_error(style_error: str, has_logo: bool) -> str:
    """segno wants a lowercase error level. A logo punches a hole in the QR, so
    we force the highest error correction (H, ~30% recoverable) whenever a logo
    is present, regardless of what the user picked."""
    return "h" if has_logo else style_error.lower()


def make_symbol(encoded_text: str, error: str, has_logo: bool) -> segno.QRCode:
    """Build the segno QR symbol (the abstract module matrix, no pixels yet)."""
    return segno.make(encoded_text, error=_effective_error(error, has_logo))


# ---------------------------------------------------------------------------
# Logo handling
# ---------------------------------------------------------------------------
def validate_logo(raw: bytes) -> Image.Image:
    """Validate an uploaded logo and return it as a PIL image.

    Checks: size cap, decodable image, allowed format, sane dimensions. We fully
    re-encode the image later, so we never trust or pass through the original
    bytes (which could carry a malicious payload disguised as an image)."""
    if len(raw) > settings.max_logo_bytes:
        raise PayloadError(f"Logo is too large (max {settings.max_logo_bytes // 1024} KB)")
    try:
        img = Image.open(io.BytesIO(raw))
        img.verify()               # cheap integrity check
        img = Image.open(io.BytesIO(raw))  # reopen; verify() leaves the file unusable
    except Exception:
        raise PayloadError("Logo is not a valid image")
    if img.format not in _ALLOWED_LOGO_FORMATS:
        raise PayloadError("Logo must be a PNG, JPG, or WEBP image")
    if max(img.size) > settings.max_logo_dimension:
        raise PayloadError("Logo image dimensions are too large")
    return img.convert("RGBA")


def _embed_logo(qr_img: Image.Image, logo: Image.Image, bg_color: str) -> Image.Image:
    """Composite a logo into the centre of a rendered QR image.

    We deliberately do NOT just slap a big logo on top. We:
      1. size the logo to at most _LOGO_MAX_FRACTION of the QR width,
      2. paint a slightly larger solid patch behind it (in the QR's background
         colour) so the logo sits in a clean quiet area instead of on top of
         data modules, and
      3. rely on error-correction level H (forced when a logo is present) to
         recover the modules the patch covers.
    """
    qr_img = qr_img.convert("RGBA")
    qr_w, qr_h = qr_img.size

    logo_side = int(qr_w * _LOGO_MAX_FRACTION)
    logo = logo.copy()
    logo.thumbnail((logo_side, logo_side), Image.LANCZOS)
    lw, lh = logo.size

    patch_side = int(max(lw, lh) * 1.18)
    patch = Image.new("RGBA", (patch_side, patch_side), bg_color)
    px = (qr_w - patch_side) // 2
    py = (qr_h - patch_side) // 2
    qr_img.paste(patch, (px, py), patch)

    lx = (qr_w - lw) // 2
    ly = (qr_h - lh) // 2
    qr_img.paste(logo, (lx, ly), logo)
    return qr_img


def render_png(encoded_text: str, style: dict, logo: Image.Image | None = None) -> bytes:
    """Render a QR to PNG bytes with colours, scale, quiet zone, and optional logo."""
    has_logo = logo is not None
    symbol = make_symbol(encoded_text, style.get("error", "M"), has_logo)

    buf = io.BytesIO()
    symbol.save(
        buf,
        kind="png",
        scale=style.get("scale", 10),
        border=style.get("border", 4),
        dark=style.get("fg_color", "#000000"),
        light=style.get("bg_color", "#ffffff"),
    )
    buf.seek(0)
    img = Image.open(buf).convert("RGBA")

    if has_logo:
        img = _embed_logo(img, logo, style.get("bg_color", "#ffffff"))

    out = io.BytesIO()
    img.convert("RGB").save(out, format="PNG")
    return out.getvalue()


# ---------------------------------------------------------------------------
# Readability warnings and verification
# ---------------------------------------------------------------------------
def _hex_to_lum(hex_color: str) -> float:
    """Relative luminance (0=black,1=white) of a #rgb/#rrggbb colour."""
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def scannability_warnings(style: dict, has_logo: bool) -> list[dict]:
    """Return non-fatal warnings if the chosen options may hurt scanning.

    A QR scanner needs strong contrast between the dark modules and the light
    background, a quiet zone around the code, and enough error correction to
    survive a logo. We surface these instead of silently producing a pretty but
    unscannable code."""
    warnings: list[dict] = []
    contrast = abs(_hex_to_lum(style.get("fg_color", "#000000")) - _hex_to_lum(style.get("bg_color", "#ffffff")))
    if contrast < 0.4:
        warnings.append({
            "level": "warning",
            "message": "Low contrast between foreground and background may make this QR hard to scan.",
        })
    if _hex_to_lum(style.get("fg_color", "#000000")) > _hex_to_lum(style.get("bg_color", "#ffffff")):
        warnings.append({
            "level": "warning",
            "message": "Foreground is lighter than the background (inverted). Many scanners expect dark-on-light.",
        })
    if style.get("border", 4) < 4:
        warnings.append({
            "level": "info",
            "message": "The quiet zone (border) is below the recommended 4 modules.",
        })
    if has_logo and style.get("error", "M") != "H":
        warnings.append({
            "level": "info",
            "message": "Error correction was raised to H automatically to keep the code scannable with a logo.",
        })
    return warnings


def decode_png(png_bytes: bytes) -> str | None:
    """Decode a QR image back to its text using OpenCV, or None if it can't be
    read. Used to VERIFY that what we generated actually scans to the expected
    payload. OpenCV is self-contained (no system zbar dependency), which keeps
    the Docker image simple."""
    arr = np.frombuffer(png_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return None
    detector = cv2.QRCodeDetector()
    data, points, _ = detector.detectAndDecode(img)
    return data or None


def verify_png(png_bytes: bytes, expected_text: str) -> bool:
    """True if the rendered QR decodes back to exactly the expected text."""
    return decode_png(png_bytes) == expected_text


def logo_to_base64(logo_bytes: bytes) -> str:
    return base64.b64encode(logo_bytes).decode("ascii")


def base64_to_logo(data: str) -> Image.Image:
    return validate_logo(base64.b64decode(data))
