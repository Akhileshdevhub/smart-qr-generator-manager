"""QR project routes: CRUD, live preview, logo upload, and downloads.

Static vs dynamic is decided at creation and is immutable afterwards:
  * dynamic requires qr_type == "url"; we store the editable destination and
    encode our own /r/<short_id> endpoint into the image.
  * static encodes the content directly; editing content would change the image,
    so we only allow name/style edits on static codes.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_owned_project
from app.core.config import settings
from app.core.logging_config import get_logger
from app.core.rate_limit import limiter
from app.db.database import get_db
from app.db.models import QRProject, User
from app.schemas.qr import QRCreate, QROut, QRPreview, QRUpdate
from app.services import analytics_service, export_service, qr_service
from app.services.payloads import (
    PayloadError,
    build_payload,
    describe_destination,
    validate_destination_url,
)

router = APIRouter(prefix="/api/qr", tags=["qr"])
logger = get_logger("qr")


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------
def project_to_out(db: Session, project: QRProject) -> QROut:
    """Build the API response for a project, adding computed fields that aren't
    stored columns (scan count, logo flag, redirect URL)."""
    out = QROut.model_validate(project)
    out.scan_count = analytics_service.scan_count_for(db, project.id)
    out.has_logo = bool(project.logo_data)
    if project.mode == "dynamic":
        out.redirect_url = f"{settings.base_url}/r/{project.short_id}"
    # Show the human-readable destination even for static codes.
    if not out.destination_url:
        out.destination_url = describe_destination(project.qr_type, project.content)
    return out


def _unique_short_id(db: Session) -> str:
    """Generate a short id, retrying on the (very unlikely) collision."""
    for _ in range(5):
        candidate = qr_service.generate_short_id()
        if db.scalar(select(QRProject.id).where(QRProject.short_id == candidate)) is None:
            return candidate
    raise HTTPException(status_code=500, detail="Could not allocate a unique id, please retry")


# ---------------------------------------------------------------------------
# Preview (no auth, no DB): render options live while the user types
# ---------------------------------------------------------------------------
@router.post("/preview", responses={200: {"content": {"image/png": {}}}})
@limiter.limit("60/minute")
def preview(request: Request, payload: QRPreview):
    """Render a PNG for the given options without saving anything. Powers the
    live preview in the generator and a demo on the landing page."""
    try:
        if payload.mode == "dynamic":
            if payload.qr_type != "url":
                raise PayloadError("Dynamic mode is only available for URL codes")
            dest = validate_destination_url(payload.destination_url or payload.content.get("url", ""))
            # A preview can't know a real short id yet; show a representative URL.
            encoded = f"{settings.base_url}/r/XXXXXXX"
            _ = dest  # validated for early feedback
        else:
            encoded = build_payload(payload.qr_type, payload.content)
    except PayloadError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    style = payload.style.model_dump()
    png = export_service.to_png(encoded, style)
    # Pass readability warnings back in a header so the live preview can show
    # them without a second request.
    import json
    warnings = qr_service.scannability_warnings(style, has_logo=False)
    return Response(
        content=png,
        media_type="image/png",
        headers={"X-Scan-Warnings": json.dumps(warnings)},
    )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
@router.post("", response_model=QROut, status_code=status.HTTP_201_CREATED)
def create_qr(
    payload: QRCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    short_id = _unique_short_id(db)

    try:
        if payload.mode == "dynamic":
            if payload.qr_type != "url":
                raise PayloadError("Dynamic mode is only available for URL codes")
            dest = validate_destination_url(payload.destination_url or payload.content.get("url", ""))
            content = {"url": dest}
            destination_url = dest
        else:
            # Validate now so we never store content that can't be encoded.
            build_payload(payload.qr_type, payload.content)
            content = payload.content
            destination_url = None
    except PayloadError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    project = QRProject(
        short_id=short_id,
        owner_id=current_user.id,
        name=payload.name,
        qr_type=payload.qr_type,
        mode=payload.mode,
        content=content,
        destination_url=destination_url,
        style=payload.style.model_dump(),
        active=True,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    logger.info("qr created id=%s mode=%s type=%s owner=%s",
                project.id, project.mode, project.qr_type, current_user.id)
    return project_to_out(db, project)


@router.get("", response_model=list[QROut])
def list_qr(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    projects = db.scalars(
        select(QRProject).where(QRProject.owner_id == current_user.id).order_by(QRProject.created_at.desc())
    )
    return [project_to_out(db, p) for p in projects]


@router.get("/{qr_id}", response_model=QROut)
def get_qr(project: QRProject = Depends(get_owned_project), db: Session = Depends(get_db)):
    return project_to_out(db, project)


@router.put("/{qr_id}", response_model=QROut)
def update_qr(
    payload: QRUpdate,
    project: QRProject = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    if payload.name is not None:
        project.name = payload.name
    if payload.active is not None:
        project.active = payload.active
    if payload.style is not None:
        project.style = payload.style.model_dump()

    if payload.destination_url is not None:
        # Only dynamic codes have an editable destination. Changing it here does
        # NOT change short_id or the image — that is the whole point.
        if project.mode != "dynamic":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Only dynamic QR codes have an editable destination",
            )
        try:
            dest = validate_destination_url(payload.destination_url)
        except PayloadError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
        project.destination_url = dest
        project.content = {"url": dest}

    db.commit()
    db.refresh(project)
    return project_to_out(db, project)


@router.delete("/{qr_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_qr(project: QRProject = Depends(get_owned_project), db: Session = Depends(get_db)):
    db.delete(project)   # cascades to scan events
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{qr_id}/duplicate", response_model=QROut, status_code=status.HTTP_201_CREATED)
def duplicate_qr(project: QRProject = Depends(get_owned_project), db: Session = Depends(get_db)):
    """Copy a project into a brand-new one (new short_id, fresh analytics)."""
    clone = QRProject(
        short_id=_unique_short_id(db),
        owner_id=project.owner_id,
        name=f"{project.name} (copy)",
        qr_type=project.qr_type,
        mode=project.mode,
        content=dict(project.content),
        destination_url=project.destination_url,
        style=dict(project.style),
        logo_data=project.logo_data,
        active=True,
    )
    db.add(clone)
    db.commit()
    db.refresh(clone)
    return project_to_out(db, clone)


# ---------------------------------------------------------------------------
# Logo upload
# ---------------------------------------------------------------------------
@router.post("/{qr_id}/logo", response_model=QROut)
async def upload_logo(
    file: UploadFile,
    project: QRProject = Depends(get_owned_project),
    db: Session = Depends(get_db),
):
    raw = await file.read()
    try:
        qr_service.validate_logo(raw)   # validate before storing
    except PayloadError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    project.logo_data = qr_service.logo_to_base64(raw)
    db.commit()
    db.refresh(project)
    return project_to_out(db, project)


@router.delete("/{qr_id}/logo", response_model=QROut)
def remove_logo(project: QRProject = Depends(get_owned_project), db: Session = Depends(get_db)):
    project.logo_data = None
    db.commit()
    db.refresh(project)
    return project_to_out(db, project)


# ---------------------------------------------------------------------------
# Rendered image + downloads
# ---------------------------------------------------------------------------
def _encoded_and_logo(project: QRProject):
    encoded = qr_service.encoded_text_for(
        project.qr_type, project.content, project.mode, project.short_id
    )
    logo = None
    logo_bytes = None
    if project.logo_data:
        import base64
        logo_bytes = base64.b64decode(project.logo_data)
        logo = qr_service.validate_logo(logo_bytes)
    return encoded, logo, logo_bytes


@router.get("/{qr_id}/image")
def rendered_image(project: QRProject = Depends(get_owned_project)):
    """Return the saved QR as a PNG (with logo if one is attached). Used by the
    app to show the real, saved image."""
    encoded, logo, _ = _encoded_and_logo(project)
    png = export_service.to_png(encoded, project.style, logo)
    return Response(content=png, media_type="image/png")


@router.get("/{qr_id}/download")
def download(fmt: str = "png", project: QRProject = Depends(get_owned_project)):
    """Download the QR as png | svg | pdf."""
    fmt = fmt.lower()
    if fmt not in {"png", "svg", "pdf"}:
        raise HTTPException(status_code=422, detail="format must be png, svg, or pdf")

    encoded, logo, logo_bytes = _encoded_and_logo(project)
    safe_name = "".join(c for c in project.name if c.isalnum() or c in "-_ ").strip().replace(" ", "_") or "qr"

    if fmt == "png":
        data = export_service.to_png(encoded, project.style, logo)
        media = "image/png"
    elif fmt == "svg":
        data = export_service.to_svg(encoded, project.style, logo_bytes)
        media = "image/svg+xml"
    else:
        label = project.destination_url or describe_destination(project.qr_type, project.content)
        data = export_service.to_pdf(encoded, project.style, project.name, label, logo_bytes)
        media = "application/pdf"

    headers = {"Content-Disposition": f'attachment; filename="{safe_name}.{fmt}"'}
    return Response(content=data, media_type=media, headers=headers)


@router.get("/{qr_id}/verify")
def verify(project: QRProject = Depends(get_owned_project)):
    """Decode the generated PNG and confirm it scans back to the expected text.
    Exposes the same verification the test-suite uses, so the UI can show a
    'verified scannable' badge based on a real decode, not a claim."""
    encoded, logo, _ = _encoded_and_logo(project)
    png = export_service.to_png(encoded, project.style, logo)
    decoded = qr_service.decode_png(png)
    return {"expected": encoded, "decoded": decoded, "verified": decoded == encoded}
