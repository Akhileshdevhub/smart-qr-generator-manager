"""Record scan events and aggregate them for the dashboards.

Privacy is the design driver here (see docs/analytics.md and the in-app privacy
notice):

  * We never store a raw IP address. We store sha256(secret + ip)[:16] — enough
    to loosely count/deduplicate, impossible to reverse back to an address.
  * We store only *coarse* derived fields: device category (mobile/tablet/
    desktop/bot), browser family, OS family, and an optional country string.
  * Time-series aggregation is done in Python after a single ranged query. This
    keeps the SQL database-agnostic (SQLite in dev, Postgres in prod) instead of
    relying on vendor-specific date functions, which is fine at this scale.
"""
import hashlib
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from user_agents import parse as parse_ua

from app.core.config import settings
from app.core.logging_config import get_logger
from app.db.models import QRProject, ScanEvent

logger = get_logger("analytics")


def hash_ip(ip: str | None) -> str | None:
    """One-way, salted hash of an IP. The app secret is the salt, so the hash
    can't be pre-computed with a rainbow table of all IPv4 addresses."""
    if not ip:
        return None
    digest = hashlib.sha256((settings.secret_key + ip).encode("utf-8")).hexdigest()
    return digest[:16]


def classify_user_agent(ua_string: str | None) -> tuple[str, str, str]:
    """Return (device_type, browser_family, os_family) from a User-Agent string."""
    if not ua_string:
        return "unknown", "unknown", "unknown"
    ua = parse_ua(ua_string)
    if ua.is_bot:
        device = "bot"
    elif ua.is_mobile:
        device = "mobile"
    elif ua.is_tablet:
        device = "tablet"
    elif ua.is_pc:
        device = "desktop"
    else:
        device = "unknown"
    return device, (ua.browser.family or "unknown"), (ua.os.family or "unknown")


def record_scan(
    db: Session,
    project: QRProject,
    ip: str | None = None,
    user_agent: str | None = None,
    referrer: str | None = None,
    country: str | None = None,
    is_demo: bool = False,
) -> ScanEvent:
    """Persist one scan event with only privacy-safe, coarse fields."""
    device, browser, os_family = classify_user_agent(user_agent)
    event = ScanEvent(
        qr_id=project.id,
        device_type=device,
        browser=browser,
        operating_system=os_family,
        country=country,
        referrer=(referrer or None),
        ip_hash=hash_ip(ip),
        is_demo=is_demo,
    )
    db.add(event)
    db.commit()
    logger.info("scan recorded qr_id=%s device=%s", project.id, device)
    return event


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    """SQLite hands back naive datetimes; treat them as UTC for comparisons."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _count_since(events: list[ScanEvent], since: datetime) -> int:
    return sum(1 for e in events if _as_utc(e.timestamp) >= since)


def _time_series(events: list[ScanEvent], days: int) -> list[dict]:
    """Scans-per-day for the last `days` days, zero-filled so charts are continuous."""
    today = _now().date()
    buckets = {(today - timedelta(days=i)).isoformat(): 0 for i in range(days - 1, -1, -1)}
    for e in events:
        key = _as_utc(e.timestamp).date().isoformat()
        if key in buckets:
            buckets[key] += 1
    return [{"date": d, "count": c} for d, c in buckets.items()]


def _breakdown(events: list[ScanEvent], attr: str, top: int = 6) -> list[dict]:
    counter = Counter(getattr(e, attr) or "unknown" for e in events)
    return [{"label": label, "count": count} for label, count in counter.most_common(top)]


def qr_analytics(db: Session, project: QRProject) -> dict:
    events = list(db.scalars(select(ScanEvent).where(ScanEvent.qr_id == project.id)))
    now = _now()
    return {
        "qr_id": project.id,
        "name": project.name,
        "total_scans": len(events),
        "scans_today": _count_since(events, now.replace(hour=0, minute=0, second=0, microsecond=0)),
        "scans_this_week": _count_since(events, now - timedelta(days=7)),
        "scans_over_time": _time_series(events, days=14),
        "device_breakdown": _breakdown(events, "device_type"),
        "browser_breakdown": _breakdown(events, "browser"),
        "country_breakdown": _breakdown(events, "country"),
        "contains_demo_data": any(e.is_demo for e in events),
    }


def dashboard_overview(db: Session, user_id: int) -> dict:
    """Account-wide overview across all of a user's QR projects."""
    projects = list(db.scalars(select(QRProject).where(QRProject.owner_id == user_id)))
    project_ids = [p.id for p in projects]

    events: list[ScanEvent] = []
    if project_ids:
        events = list(db.scalars(select(ScanEvent).where(ScanEvent.qr_id.in_(project_ids))))

    now = _now()
    # Scans per project, for the "top QR" list.
    per_project = Counter(e.qr_id for e in events)
    top = sorted(projects, key=lambda p: per_project.get(p.id, 0), reverse=True)[:5]

    return {
        "total_qr": len(projects),
        "active_qr": sum(1 for p in projects if p.active),
        "total_scans": len(events),
        "scans_today": _count_since(events, now.replace(hour=0, minute=0, second=0, microsecond=0)),
        "scans_this_week": _count_since(events, now - timedelta(days=7)),
        "scans_over_time": _time_series(events, days=14),
        "top_qr": [
            {"id": p.id, "name": p.name, "short_id": p.short_id, "scan_count": per_project.get(p.id, 0)}
            for p in top
        ],
    }


def scan_count_for(db: Session, qr_id: int) -> int:
    return db.scalar(select(func.count()).select_from(ScanEvent).where(ScanEvent.qr_id == qr_id)) or 0
