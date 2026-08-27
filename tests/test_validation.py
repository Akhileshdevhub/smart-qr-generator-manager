"""Input validation: URL schemes, payload rules, and logo uploads."""
import io

import pytest
from PIL import Image

from app.services.payloads import PayloadError, build_payload, validate_destination_url
from app.services.qr_service import validate_logo
from tests.conftest import auth_headers


# --- URL scheme validation (security-critical) ---
@pytest.mark.parametrize("bad", [
    "javascript:alert(1)",
    "data:text/html,<script>alert(1)</script>",
    "file:///etc/passwd",
    "ftp://example.com",
    "not-a-url",
    "",
])
def test_dangerous_or_malformed_urls_rejected(bad):
    with pytest.raises(PayloadError):
        validate_destination_url(bad)


@pytest.mark.parametrize("good", ["http://example.com", "https://example.com/path?q=1"])
def test_valid_urls_accepted(good):
    assert validate_destination_url(good) == good


def test_bad_url_rejected_by_api(client):
    h = auth_headers(client)
    r = client.post("/api/qr", headers=h, json={
        "name": "x", "qr_type": "url", "mode": "static", "content": {"url": "javascript:alert(1)"},
    })
    assert r.status_code == 422


# --- payload validation per type ---
def test_wifi_requires_ssid():
    with pytest.raises(PayloadError):
        build_payload("wifi", {"password": "x", "encryption": "WPA"})


def test_wifi_special_characters_escaped():
    payload = build_payload("wifi", {"ssid": "My;Net", "password": "a,b", "encryption": "WPA"})
    assert "My\\;Net" in payload
    assert "a\\,b" in payload


def test_vcard_requires_name():
    with pytest.raises(PayloadError):
        build_payload("vcard", {"email": "x@y.com"})


def test_email_builds_mailto():
    payload = build_payload("email", {"to": "a@b.com", "subject": "Hi there", "body": "Yo"})
    assert payload.startswith("mailto:a@b.com?")
    assert "subject=Hi%20there" in payload


# --- logo validation ---
def _png_bytes(size=(120, 120)):
    buf = io.BytesIO()
    Image.new("RGB", size, "#123456").save(buf, format="PNG")
    return buf.getvalue()


def test_valid_logo_accepted():
    img = validate_logo(_png_bytes())
    assert img.mode == "RGBA"


def test_non_image_rejected():
    with pytest.raises(PayloadError):
        validate_logo(b"this is not an image")


def test_logo_upload_endpoint(client):
    h = auth_headers(client)
    qr = client.post("/api/qr", headers=h, json={
        "name": "x", "qr_type": "url", "mode": "static", "content": {"url": "https://example.com"},
    }).json()
    files = {"file": ("logo.png", _png_bytes(), "image/png")}
    r = client.post(f"/api/qr/{qr['id']}/logo", headers=h, files=files)
    assert r.status_code == 200
    assert r.json()["has_logo"] is True


def test_oversized_logo_rejected(client):
    h = auth_headers(client)
    qr = client.post("/api/qr", headers=h, json={
        "name": "x", "qr_type": "url", "mode": "static", "content": {"url": "https://example.com"},
    }).json()
    big = b"\x89PNG" + b"0" * (3 * 1024 * 1024)  # > 2 MB cap
    files = {"file": ("big.png", big, "image/png")}
    r = client.post(f"/api/qr/{qr['id']}/logo", headers=h, files=files)
    assert r.status_code == 422
