"""The public dynamic-redirect endpoint: GET /r/<short_id>.

This is the only endpoint a scanner's phone talks to. It is deliberately
unauthenticated (anyone can scan a printed code), but it is careful:

    scan -> look up short_id -> check the code is active
         -> record a privacy-safe analytics event
         -> validate the stored destination is still http(s)
         -> 302 redirect to the current destination

Because dynamic codes encode this endpoint (not the final URL), the owner can
change the destination anytime and every already-printed code follows along.
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.logging_config import get_logger
from app.core.rate_limit import limiter
from app.db.database import get_db
from app.services import analytics_service, redirect_service

router = APIRouter(tags=["redirect"])
logger = get_logger("redirect")


def _client_ip(request: Request) -> str | None:
    """Best-effort client IP. Behind a proxy, X-Forwarded-For's first entry is
    the original client. We only ever hash this value, never store it raw."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else None


def _message(title: str, body: str, code: int) -> HTMLResponse:
    html = f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>body{{font-family:system-ui,sans-serif;background:#f5f6f8;color:#1a1a2e;
display:flex;min-height:100vh;align-items:center;justify-content:center;margin:0}}
.card{{background:#fff;padding:40px;border-radius:10px;box-shadow:0 1px 4px rgba(0,0,0,.1);
max-width:420px;text-align:center}}h1{{margin:0 0 8px;font-size:20px}}p{{color:#555}}</style>
</head><body><div class="card"><h1>{title}</h1><p>{body}</p></div></body></html>"""
    return HTMLResponse(content=html, status_code=code)


@router.get("/r/{short_id}")
@limiter.limit("120/minute")
def follow_redirect(short_id: str, request: Request, db: Session = Depends(get_db)):
    try:
        project = redirect_service.resolve_project(db, short_id)
    except redirect_service.RedirectNotFound:
        return _message("Link not found", "This QR code does not exist or has been removed.", 404)
    except redirect_service.RedirectInactive:
        return _message("Link disabled", "The owner has deactivated this QR code.", 410)

    try:
        destination = redirect_service.destination_for(project)
    except redirect_service.RedirectInvalidTarget:
        return _message("Link unavailable", "This QR code has no valid destination set.", 409)

    # Record the scan. We swallow analytics errors so a logging hiccup never
    # blocks the redirect the user actually cares about.
    try:
        analytics_service.record_scan(
            db,
            project,
            ip=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            referrer=request.headers.get("referer"),
        )
    except Exception:  # pragma: no cover - defensive
        logger.exception("failed to record scan for %s", short_id)

    return RedirectResponse(url=destination, status_code=302)
