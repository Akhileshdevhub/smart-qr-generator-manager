"""Dynamic redirect behaviour and its relationship to the QR image."""
from tests.conftest import auth_headers, make_qr


def _dynamic(client, headers, dest="https://example.com/menu"):
    return client.post("/api/qr", headers=headers, json={
        "name": "Menu", "qr_type": "url", "mode": "dynamic", "destination_url": dest,
    }).json()


def test_redirect_forwards_to_destination(client):
    h = auth_headers(client)
    qr = _dynamic(client, h)
    r = client.get(f"/r/{qr['short_id']}", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "https://example.com/menu"


def test_changing_destination_keeps_short_id_and_image(client):
    h = auth_headers(client)
    qr = _dynamic(client, h)
    old_short = qr["short_id"]

    updated = client.put(f"/api/qr/{qr['id']}", headers=h,
                         json={"destination_url": "https://example.com/new"}).json()
    # The whole point of dynamic QR: the short_id (and therefore the image) is unchanged.
    assert updated["short_id"] == old_short

    r = client.get(f"/r/{old_short}", follow_redirects=False)
    assert r.headers["location"] == "https://example.com/new"


def test_inactive_qr_does_not_redirect(client):
    h = auth_headers(client)
    qr = _dynamic(client, h)
    client.put(f"/api/qr/{qr['id']}", headers=h, json={"active": False})
    assert client.get(f"/r/{qr['short_id']}", follow_redirects=False).status_code == 410


def test_deleted_qr_does_not_redirect(client):
    h = auth_headers(client)
    qr = _dynamic(client, h)
    client.delete(f"/api/qr/{qr['id']}", headers=h)
    assert client.get(f"/r/{qr['short_id']}", follow_redirects=False).status_code == 404


def test_unknown_short_id_returns_404(client):
    assert client.get("/r/nope123", follow_redirects=False).status_code == 404


def test_scan_is_recorded(client):
    h = auth_headers(client)
    qr = _dynamic(client, h)
    client.get(f"/r/{qr['short_id']}", headers={"User-Agent": "Mozilla/5.0 (iPhone)"}, follow_redirects=False)
    analytics = client.get(f"/api/qr/{qr['id']}/analytics", headers=h).json()
    assert analytics["total_scans"] == 1
    assert analytics["device_breakdown"][0]["label"] == "mobile"


def test_static_qr_only_url_can_be_dynamic(client):
    """Dynamic mode is only valid for URL codes."""
    h = auth_headers(client)
    r = client.post("/api/qr", headers=h, json={
        "name": "bad", "qr_type": "wifi", "mode": "dynamic", "content": {"ssid": "x", "password": "y"},
    })
    assert r.status_code == 422
