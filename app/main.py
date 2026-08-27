"""FastAPI application entry point.

Wires together configuration, the database, the REST routers, the public
redirect endpoint, rate limiting, and the static frontend. Run with:

    uvicorn app.main:app --reload
"""
from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import PROJECT_ROOT, settings
from app.core.logging_config import configure_logging, get_logger
from app.core.rate_limit import limiter
from app.db.database import create_all_tables
from app.api.routes import analytics, auth, qr, redirect

configure_logging()
logger = get_logger("main")

FRONTEND_DIR = PROJECT_ROOT / "frontend"

DESCRIPTION = """
REST API for the Smart QR Generator & Manager.

Create static and dynamic QR codes, customise and export them (PNG/SVG/PDF),
manage saved projects, and view privacy-conscious scan analytics for dynamic
codes.

**Authentication:** register, then log in at `/api/auth/login` to receive a JWT.
Send it as `Authorization: Bearer <token>` on protected endpoints (use the
**Authorize** button above).
"""

# docs_url=None: we serve Swagger UI ourselves from vendored assets (below) so
# the interactive API docs work offline, without a CDN.
app = FastAPI(
    title="Smart QR Generator & Manager",
    description=DESCRIPTION,
    version="1.0.0",
    contact={"name": "Project API"},
    docs_url=None,
    redoc_url=None,
)

# --- Rate limiting ---
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


@app.exception_handler(RateLimitExceeded)
def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded, please slow down."})


@app.exception_handler(Exception)
def _unhandled_handler(request: Request, exc: Exception):
    # Never leak a stack trace to the client; log it server-side instead.
    logger.exception("unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.on_event("startup")
def on_startup():
    create_all_tables()
    logger.info("Smart QR Manager started (env=%s, base_url=%s)", settings.environment, settings.base_url)


# --- API routers ---
app.include_router(auth.router)
app.include_router(qr.router)
app.include_router(analytics.router)
app.include_router(redirect.router)   # public /r/<short_id>


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


@app.get("/docs", include_in_schema=False)
def custom_swagger_ui():
    """Interactive API docs served from locally vendored Swagger UI assets."""
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} — API docs",
        swagger_js_url="/static/vendor/swagger/swagger-ui-bundle.js",
        swagger_css_url="/static/vendor/swagger/swagger-ui.css",
    )


# --- Frontend (static pages) ---
# Served by FastAPI in development for a single-command run. In production you
# would typically put these behind a CDN / nginx and keep the API separate.
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


def _page(name: str) -> FileResponse:
    return FileResponse(FRONTEND_DIR / name)


@app.get("/", include_in_schema=False)
def landing():
    return _page("index.html")


@app.get("/login", include_in_schema=False)
def login_page():
    return _page("login.html")


@app.get("/register", include_in_schema=False)
def register_page():
    return _page("register.html")


@app.get("/app", include_in_schema=False)
def app_page():
    return _page("app.html")


@app.get("/privacy", include_in_schema=False)
def privacy_page():
    return _page("privacy.html")
