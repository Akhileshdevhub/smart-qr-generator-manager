"""Resolve a dynamic-QR short id to its current destination, safely.

This is the public, unauthenticated path a phone hits when it scans a dynamic
QR: GET /r/<short_id>. Anyone can scan, so there is no login here — but we still
validate carefully because we are about to send someone's browser to a stored
URL.
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import QRProject
from app.services.payloads import PayloadError, validate_destination_url


class RedirectNotFound(Exception):
    """No project with this short id."""


class RedirectInactive(Exception):
    """The project exists but has been deactivated/archived by its owner."""


class RedirectInvalidTarget(Exception):
    """The stored destination is somehow no longer a safe http(s) URL."""


def resolve_project(db: Session, short_id: str) -> QRProject:
    project = db.scalar(select(QRProject).where(QRProject.short_id == short_id))
    if project is None:
        raise RedirectNotFound(short_id)
    if not project.active:
        # A deleted/disabled QR must stop redirecting even though the printed
        # image still exists in the world.
        raise RedirectInactive(short_id)
    return project


def destination_for(project: QRProject) -> str:
    """Return the validated URL to redirect to.

    We re-validate the scheme on every scan (defence in depth) so that even if a
    bad value somehow reached the DB, we never redirect a scanner to a
    javascript:/data: URL.
    """
    target = project.destination_url
    if not target:
        raise RedirectInvalidTarget("no destination set")
    try:
        return validate_destination_url(target)
    except PayloadError as exc:
        raise RedirectInvalidTarget(str(exc))
