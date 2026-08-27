"""Registration and login."""
from tests.conftest import auth_headers


def test_register_and_login(client):
    r = client.post("/api/auth/register", json={"email": "a@x.com", "password": "password123"})
    assert r.status_code == 201
    assert r.json()["email"] == "a@x.com"
    assert "password" not in r.json()  # never echo the password/hash

    r = client.post("/api/auth/login", json={"email": "a@x.com", "password": "password123"})
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"
    assert r.json()["access_token"]


def test_duplicate_email_rejected(client):
    client.post("/api/auth/register", json={"email": "a@x.com", "password": "password123"})
    r = client.post("/api/auth/register", json={"email": "a@x.com", "password": "password123"})
    assert r.status_code == 409


def test_wrong_password(client):
    client.post("/api/auth/register", json={"email": "a@x.com", "password": "password123"})
    r = client.post("/api/auth/login", json={"email": "a@x.com", "password": "wrong-password"})
    assert r.status_code == 401


def test_short_password_rejected(client):
    r = client.post("/api/auth/register", json={"email": "a@x.com", "password": "short"})
    assert r.status_code == 422  # fails the min_length=8 schema rule


def test_me_requires_auth(client):
    assert client.get("/api/auth/me").status_code == 401
    headers = auth_headers(client)
    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200


def test_password_is_hashed_in_db(client):
    """The stored password must be a bcrypt hash, never the plaintext."""
    from tests.conftest import TestingSessionLocal
    from app.db.models import User

    client.post("/api/auth/register", json={"email": "h@x.com", "password": "password123"})
    with TestingSessionLocal() as db:
        user = db.query(User).filter_by(email="h@x.com").one()
        assert user.password_hash != "password123"
        assert user.password_hash.startswith("$2")  # bcrypt hash prefix
