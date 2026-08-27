"""SQLAlchemy ORM models: User, QRProject, ScanEvent.

Design notes
------------
* Three tables only. We resisted adding a separate `GeneratedAsset` table:
  QR images are cheap to regenerate on demand from the stored payload + style,
  so caching them in the DB would add complexity without a measured benefit
  (see docs/limitations.md, "Performance").
* `QRProject.content` and `.style` are JSON columns. A URL QR needs one field, a
  vCard needs six; a JSON blob keeps the schema simple instead of a wide table
  full of mostly-NULL columns. The trade-off is we can't query *inside* the
  payload in SQL, which we never need to.
* `short_id` is a random string used in the public redirect URL (/r/<short_id>),
  NOT the primary key. Exposing sequential integer ids would let anyone
  enumerate every QR by counting up; a random id can't be guessed.
* Indexes are placed on the columns we actually filter/join on:
  users.email (login lookup), qr_projects.short_id (every redirect),
  qr_projects.owner_id (listing a user's projects), scan_events.qr_id and
  scan_events.timestamp (analytics aggregation).
"""
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def _utcnow() -> datetime:
    """Timezone-aware UTC timestamp. We store everything in UTC and format to
    the user's locale in the frontend."""
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    # bcrypt hash, never the plaintext password.
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    projects: Mapped[list["QRProject"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )


class QRProject(Base):
    __tablename__ = "qr_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Public, unguessable id used in dynamic redirect URLs.
    short_id: Mapped[str] = mapped_column(String(16), unique=True, index=True, nullable=False)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    qr_type: Mapped[str] = mapped_column(String(20), nullable=False)   # url|text|wifi|vcard|email|phone
    mode: Mapped[str] = mapped_column(String(10), nullable=False)      # static|dynamic

    # Payload fields for the content type (JSON). For a dynamic URL project the
    # user-facing target also lives in `destination_url` so we can update it
    # without touching the encoded image.
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    destination_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Rendering options: foreground/background colour, scale, border, error level, logo flag.
    style: Mapped[dict] = mapped_column(JSON, default=dict)
    logo_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # base64 PNG of the uploaded logo

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    owner: Mapped["User"] = relationship(back_populates="projects")
    scans: Mapped[list["ScanEvent"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ScanEvent(Base):
    """One row per scan of a dynamic QR code.

    Privacy: we do NOT store the raw IP address. We store a salted+truncated
    hash so we can roughly de-duplicate/count without being able to recover the
    address, plus coarse fields (device category, browser family, OS, optional
    country). See docs/analytics.md and the in-app privacy notice.
    """
    __tablename__ = "scan_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    qr_id: Mapped[int] = mapped_column(
        ForeignKey("qr_projects.id", ondelete="CASCADE"), index=True, nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, index=True
    )

    device_type: Mapped[str] = mapped_column(String(20), default="unknown")   # mobile|tablet|desktop|bot|unknown
    browser: Mapped[str] = mapped_column(String(40), default="unknown")
    operating_system: Mapped[str] = mapped_column(String(40), default="unknown")
    country: Mapped[str | None] = mapped_column(String(60), nullable=True)
    referrer: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Privacy-safe identifier: sha256(salt + ip)[:16]. Not reversible to an IP.
    ip_hash: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # Marks rows created by the demo seed script so they are never presented as
    # real user analytics.
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    project: Mapped["QRProject"] = relationship(back_populates="scans")
