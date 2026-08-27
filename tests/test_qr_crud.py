"""Create / read / update / delete / duplicate for QR projects."""
from tests.conftest import auth_headers, make_qr


def test_create_and_get(client):
    h = auth_headers(client)
    r = make_qr(client, h, name="My site")
    assert r.status_code == 201
    body = r.json()
    assert body["mode"] == "static"
    assert len(body["short_id"]) == 7
    assert client.get(f"/api/qr/{body['id']}", headers=h).json()["name"] == "My site"


def test_update_name_and_style(client):
    h = auth_headers(client)
    qr = make_qr(client, h).json()
    r = client.put(f"/api/qr/{qr['id']}", headers=h,
                   json={"name": "Renamed", "style": {"fg_color": "#ff0000", "bg_color": "#ffffff"}})
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed"
    assert r.json()["style"]["fg_color"] == "#ff0000"


def test_delete(client):
    h = auth_headers(client)
    qr = make_qr(client, h).json()
    assert client.delete(f"/api/qr/{qr['id']}", headers=h).status_code == 204
    assert client.get(f"/api/qr/{qr['id']}", headers=h).status_code == 404


def test_duplicate_creates_new_short_id(client):
    h = auth_headers(client)
    qr = make_qr(client, h).json()
    dup = client.post(f"/api/qr/{qr['id']}/duplicate", headers=h).json()
    assert dup["short_id"] != qr["short_id"]
    assert dup["name"].endswith("(copy)")


def test_static_url_reports_destination(client):
    h = auth_headers(client)
    qr = make_qr(client, h, content={"url": "https://example.org/page"}).json()
    assert qr["destination_url"] == "https://example.org/page"
