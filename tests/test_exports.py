"""Download endpoints produce valid PNG / SVG / PDF files."""
from tests.conftest import auth_headers, make_qr


def test_png_download(client):
    h = auth_headers(client)
    qr = make_qr(client, h).json()
    r = client.get(f"/api/qr/{qr['id']}/download", params={"fmt": "png"}, headers=h)
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"  # PNG magic bytes


def test_svg_download_is_vector(client):
    h = auth_headers(client)
    qr = make_qr(client, h).json()
    r = client.get(f"/api/qr/{qr['id']}/download", params={"fmt": "svg"}, headers=h)
    assert r.status_code == 200
    assert "image/svg+xml" in r.headers["content-type"]
    body = r.content.decode()
    assert "<svg" in body
    assert "<path" in body or "<rect" in body  # actual vector shapes, not an embedded raster


def test_pdf_download(client):
    h = auth_headers(client)
    qr = make_qr(client, h).json()
    r = client.get(f"/api/qr/{qr['id']}/download", params={"fmt": "pdf"}, headers=h)
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:5] == b"%PDF-"


def test_bad_format_rejected(client):
    h = auth_headers(client)
    qr = make_qr(client, h).json()
    assert client.get(f"/api/qr/{qr['id']}/download", params={"fmt": "gif"}, headers=h).status_code == 422


def test_verify_endpoint(client):
    h = auth_headers(client)
    qr = make_qr(client, h).json()
    r = client.get(f"/api/qr/{qr['id']}/verify", headers=h).json()
    assert r["verified"] is True
    assert r["decoded"] == r["expected"]
