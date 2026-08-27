"""Ownership / authorization: users must not reach each other's QR codes."""
from tests.conftest import auth_headers, make_qr


def test_user_cannot_access_another_users_qr(client):
    a = auth_headers(client, "a@x.com")
    b = auth_headers(client, "b@x.com")

    qr_id = make_qr(client, a).json()["id"]

    # B tries to read, edit and delete A's QR by guessing the id.
    assert client.get(f"/api/qr/{qr_id}", headers=b).status_code == 404
    assert client.put(f"/api/qr/{qr_id}", headers=b, json={"name": "hijack"}).status_code == 404
    assert client.delete(f"/api/qr/{qr_id}", headers=b).status_code == 404

    # A can still access it — it was never actually modified.
    got = client.get(f"/api/qr/{qr_id}", headers=a)
    assert got.status_code == 200
    assert got.json()["name"] == "Test QR"


def test_list_only_returns_own_projects(client):
    a = auth_headers(client, "a@x.com")
    b = auth_headers(client, "b@x.com")
    make_qr(client, a)
    make_qr(client, a)
    make_qr(client, b)
    assert len(client.get("/api/qr", headers=a).json()) == 2
    assert len(client.get("/api/qr", headers=b).json()) == 1


def test_protected_routes_need_token(client):
    assert client.get("/api/qr").status_code == 401
    assert client.post("/api/qr", json={}).status_code == 401
    assert client.get("/api/analytics/overview").status_code == 401


def test_invalid_token_rejected(client):
    assert client.get("/api/qr", headers={"Authorization": "Bearer not-a-real-token"}).status_code == 401
