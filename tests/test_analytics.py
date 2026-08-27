"""Analytics recording and aggregation."""
from tests.conftest import auth_headers


def _dynamic(client, h):
    return client.post("/api/qr", headers=h, json={
        "name": "Campaign", "qr_type": "url", "mode": "dynamic", "destination_url": "https://example.com",
    }).json()


def test_overview_counts(client):
    h = auth_headers(client)
    qr = _dynamic(client, h)
    for ua in ["Mozilla/5.0 (iPhone)", "Mozilla/5.0 (Windows NT 10.0)", "Mozilla/5.0 (iPhone)"]:
        client.get(f"/r/{qr['short_id']}", headers={"User-Agent": ua}, follow_redirects=False)

    ov = client.get("/api/analytics/overview", headers=h).json()
    assert ov["total_qr"] == 1
    assert ov["active_qr"] == 1
    assert ov["total_scans"] == 3
    assert ov["scans_today"] == 3
    assert len(ov["scans_over_time"]) == 14  # zero-filled 14-day window
    assert ov["top_qr"][0]["scan_count"] == 3


def test_device_breakdown(client):
    h = auth_headers(client)
    qr = _dynamic(client, h)
    client.get(f"/r/{qr['short_id']}", headers={"User-Agent": "Mozilla/5.0 (iPhone)"}, follow_redirects=False)
    client.get(f"/r/{qr['short_id']}", headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64)"}, follow_redirects=False)

    a = client.get(f"/api/qr/{qr['id']}/analytics", headers=h).json()
    labels = {d["label"] for d in a["device_breakdown"]}
    assert "mobile" in labels
    assert "desktop" in labels
    assert a["contains_demo_data"] is False


def test_ip_is_not_stored_raw(client):
    """Analytics must store a hash, never the raw client IP."""
    from tests.conftest import TestingSessionLocal
    from app.db.models import ScanEvent

    h = auth_headers(client)
    qr = _dynamic(client, h)
    client.get(f"/r/{qr['short_id']}", headers={"User-Agent": "x", "X-Forwarded-For": "203.0.113.9"},
               follow_redirects=False)
    with TestingSessionLocal() as db:
        event = db.query(ScanEvent).first()
        assert event.ip_hash is not None
        assert event.ip_hash != "203.0.113.9"
        assert len(event.ip_hash) == 16
