"""Shared pytest fixtures.

We run the whole test suite against an in-memory SQLite database that is created
fresh for every test (so tests never interfere with each other) and injected in
place of the real database via FastAPI's dependency override system. Rate
limiting is disabled here so rapid test calls aren't throttled.
"""
import os

# Configure the app BEFORE it is imported (settings are read at import time).
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SECRET_KEY"] = "test-secret-key-that-is-long-enough-32b"
os.environ["BASE_URL"] = "http://testserver"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.rate_limit import limiter
from app.db.database import Base, get_db
from app.main import app

limiter.enabled = False  # don't throttle the test client

# One in-memory database shared across connections for the process; tables are
# dropped/recreated per test by the autouse fixture below.
engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client():
    return TestClient(app)


# --- convenience helpers -------------------------------------------------
def auth_headers(client, email="user@example.com", password="password123"):
    """Register (idempotently) + log in, returning an Authorization header."""
    client.post("/api/auth/register", json={"email": email, "password": password})
    token = client.post("/api/auth/login", json={"email": email, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def make_qr(client, headers, **overrides):
    body = {
        "name": "Test QR",
        "qr_type": "url",
        "mode": "static",
        "content": {"url": "https://example.com"},
    }
    body.update(overrides)
    return client.post("/api/qr", headers=headers, json=body)
