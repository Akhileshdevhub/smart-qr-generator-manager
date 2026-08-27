"""The important functional test: every generated QR must decode back to the
exact payload we intended to encode.

We build each content type through the real service, render a PNG, and decode it
with OpenCV. If any of these fail, we're producing pretty-but-unscannable codes.
"""
import pytest

from app.services import export_service, qr_service
from app.services.payloads import build_payload

STYLE = {"fg_color": "#000000", "bg_color": "#ffffff", "scale": 10, "border": 4, "error": "M"}


@pytest.mark.parametrize("qr_type,content,expected_substring", [
    ("url",   {"url": "https://example.com/page"}, "https://example.com/page"),
    ("text",  {"text": "Hello from my QR project"}, "Hello from my QR project"),
    ("wifi",  {"ssid": "MyNetwork", "password": "s3cr3tpass", "encryption": "WPA"}, "WIFI:"),
    ("vcard", {"name": "Ada Lovelace", "email": "ada@example.com", "phone": "+15551234567"}, "BEGIN:VCARD"),
    ("email", {"to": "hi@example.com", "subject": "Hello"}, "mailto:hi@example.com"),
    ("phone", {"phone": "+1 555 123 4567"}, "tel:+15551234567"),
])
def test_static_qr_decodes_to_payload(qr_type, content, expected_substring):
    expected = build_payload(qr_type, content)
    png = export_service.to_png(expected, STYLE)
    decoded = qr_service.decode_png(png)
    assert decoded == expected
    assert expected_substring in decoded


def test_dynamic_qr_encodes_redirect_endpoint():
    """A dynamic QR must encode our /r/<short_id> endpoint, NOT the final URL."""
    short_id = "aB3xK9p"
    encoded = qr_service.encoded_text_for("url", {"url": "https://example.com"}, "dynamic", short_id)
    assert encoded.endswith(f"/r/{short_id}")
    png = export_service.to_png(encoded, STYLE)
    assert qr_service.decode_png(png) == encoded


def test_logo_qr_still_decodes():
    """With a centre logo and error level H, the code must still scan."""
    from PIL import Image
    import io
    logo = Image.new("RGB", (200, 200), "#e63946")
    buf = io.BytesIO(); logo.save(buf, format="PNG")
    logo_img = qr_service.validate_logo(buf.getvalue())

    encoded = "https://example.com/menu"
    png = qr_service.render_png(encoded, {**STYLE, "error": "H"}, logo=logo_img)
    assert qr_service.decode_png(png) == encoded


def test_verify_helper():
    encoded = "https://example.com"
    png = export_service.to_png(encoded, STYLE)
    assert qr_service.verify_png(png, encoded) is True
    assert qr_service.verify_png(png, "https://wrong.com") is False
