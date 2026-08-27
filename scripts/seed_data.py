"""Seed the database with SAFE, SYNTHETIC demo data for local development.

Creates one demo user, a handful of representative QR projects, and — for the
dynamic ones — synthetic scan events spread over the last two weeks.

IMPORTANT: every generated scan is flagged is_demo=True so the app can label it
as synthetic. These are NOT real visitors and must never be presented as real
analytics. Run with:

    python -m scripts.seed_data        (from the project root)

Re-running wipes and recreates the demo user's data so it's idempotent.
"""
import random
import sys
from datetime import timedelta
from pathlib import Path

# Allow running as a plain script (python scripts/seed_data.py) too.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db.database import SessionLocal, create_all_tables
from app.db.models import QRProject, ScanEvent, User
from app.services import analytics_service, auth_service, qr_service

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo1234"

# Realistic User-Agent strings so device/browser classification produces variety.
USER_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 Chrome/120",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/16",
    "Mozilla/5.0 (iPad; CPU OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
]
COUNTRIES = ["India", "India", "India", "United States", "United Kingdom", "Germany"]


def _make_project(db, owner, name, qr_type, mode, content, destination=None, style=None):
    project = QRProject(
        short_id=_unique_short_id(db),
        owner_id=owner.id,
        name=name,
        qr_type=qr_type,
        mode=mode,
        content=content,
        destination_url=destination,
        style=style or {"fg_color": "#000000", "bg_color": "#ffffff", "scale": 10, "border": 4, "error": "M"},
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def _unique_short_id(db):
    while True:
        sid = qr_service.generate_short_id()
        if db.scalar(select(QRProject.id).where(QRProject.short_id == sid)) is None:
            return sid


def _seed_scans(db, project, total):
    """Create `total` synthetic scans spread over the last 14 days."""
    now = analytics_service._now()
    for _ in range(total):
        ua = random.choice(USER_AGENTS)
        device, browser, os_family = analytics_service.classify_user_agent(ua)
        days_ago = random.choices(range(14), weights=[1, 1, 2, 2, 3, 3, 4, 5, 6, 6, 7, 8, 9, 10])[0]
        ts = now - timedelta(days=days_ago, hours=random.randint(0, 23), minutes=random.randint(0, 59))
        db.add(ScanEvent(
            qr_id=project.id,
            timestamp=ts,
            device_type=device,
            browser=browser,
            operating_system=os_family,
            country=random.choice(COUNTRIES),
            ip_hash=analytics_service.hash_ip(f"10.0.0.{random.randint(1, 254)}"),
            is_demo=True,   # <-- clearly synthetic
        ))
    db.commit()


def main():
    create_all_tables()
    db = SessionLocal()
    try:
        # Reset the demo user's data so the script is re-runnable.
        existing = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        if existing:
            for p in list(existing.projects):
                db.delete(p)
            db.commit()
            user = existing
        else:
            user = auth_service.register_user(db, DEMO_EMAIL, DEMO_PASSWORD, "Demo User")

        portfolio = _make_project(
            db, user, "Portfolio Website", "url", "dynamic",
            {"url": "https://example.com"}, destination="https://example.com",
            style={"fg_color": "#1a1a2e", "bg_color": "#ffffff", "scale": 10, "border": 4, "error": "M"})
        menu = _make_project(
            db, user, "Restaurant Menu", "url", "dynamic",
            {"url": "https://example.com/menu"}, destination="https://example.com/menu",
            style={"fg_color": "#3b53d6", "bg_color": "#ffffff", "scale": 10, "border": 4, "error": "M"})
        _make_project(
            db, user, "Office Wi-Fi", "wifi", "static",
            {"ssid": "OfficeGuest", "password": "welcome123", "encryption": "WPA", "hidden": False})
        _make_project(
            db, user, "My Contact Card", "vcard", "static",
            {"name": "Demo User", "phone": "+15551234567", "email": "demo@example.com",
             "org": "Smart QR", "url": "https://example.com"})
        _make_project(
            db, user, "Event Poster Text", "text", "static", {"text": "See you at the launch!"})

        _seed_scans(db, portfolio, 240)
        _seed_scans(db, menu, 120)

        print("Seed complete (all scans are SYNTHETIC / is_demo=True).")
        print(f"  Login:    {DEMO_EMAIL} / {DEMO_PASSWORD}")
        print(f"  Projects: 5 (2 dynamic with demo scans, 3 static)")
        print(f"  Scans:    360 synthetic events across the last 14 days")
    finally:
        db.close()


if __name__ == "__main__":
    main()
