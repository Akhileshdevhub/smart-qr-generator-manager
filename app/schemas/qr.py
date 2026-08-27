"""Schemas for QR creation, update, and output.

The content payload differs by type (a URL needs one field, a vCard needs
several), so `content` is a free-form dict here and is validated field-by-field
in services/payloads.py when we build the actual QR string. Keeping the wire
schema loose but validating hard in one well-tested place avoids duplicating
six content schemas.
"""
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

QRType = Literal["url", "text", "wifi", "vcard", "email", "phone"]
QRMode = Literal["static", "dynamic"]
ErrorLevel = Literal["L", "M", "Q", "H"]

_HEX_LEN = {4, 7}  # "#fff" or "#ffffff"


class StyleOptions(BaseModel):
    """Rendering options. Defaults are chosen for maximum scannability
    (black on white, generous quiet zone, medium error correction)."""
    fg_color: str = "#000000"
    bg_color: str = "#ffffff"
    scale: int = Field(default=10, ge=2, le=40)     # pixels per module for raster output
    border: int = Field(default=4, ge=1, le=20)     # quiet-zone width in modules (4 = spec minimum)
    error: ErrorLevel = "M"

    @field_validator("fg_color", "bg_color")
    @classmethod
    def _valid_hex(cls, v: str) -> str:
        v = v.strip().lower()
        if not v.startswith("#") or len(v) not in _HEX_LEN:
            raise ValueError("colour must be a hex string like #000000")
        int(v[1:], 16)  # raises ValueError if not hex
        return v


class QRCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    qr_type: QRType
    mode: QRMode
    content: dict[str, Any] = Field(default_factory=dict)
    # Only meaningful for dynamic URL codes; the editable target the redirect points to.
    destination_url: str | None = None
    style: StyleOptions = Field(default_factory=StyleOptions)


class QRUpdate(BaseModel):
    """All fields optional: a PATCH-like update. Note there is intentionally no
    way to change `mode` or `short_id` — the whole point of a dynamic QR is that
    its printed image (and therefore its short_id) never changes."""
    name: str | None = Field(default=None, min_length=1, max_length=120)
    destination_url: str | None = None
    active: bool | None = None
    style: StyleOptions | None = None


class QRPreview(BaseModel):
    """Used by the live-preview endpoint: render without saving."""
    qr_type: QRType
    mode: QRMode
    content: dict[str, Any] = Field(default_factory=dict)
    destination_url: str | None = None
    style: StyleOptions = Field(default_factory=StyleOptions)


class QROut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    short_id: str
    name: str
    qr_type: str
    mode: str
    content: dict[str, Any]
    destination_url: str | None
    style: dict[str, Any]
    active: bool
    created_at: datetime
    updated_at: datetime
    # Extra fields the service fills in (not stored columns):
    scan_count: int = 0
    has_logo: bool = False
    redirect_url: str | None = None  # the /r/<short_id> URL for dynamic codes


class ScanWarning(BaseModel):
    """A non-fatal readability warning shown to the user after generation."""
    level: Literal["info", "warning"]
    message: str
