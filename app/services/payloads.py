"""Turn a content dict into the exact text that gets encoded into a QR code.

Each QR "type" has a standard text format that phone cameras recognise:
  * URL   -> the URL itself
  * text  -> the raw text
  * wifi  -> "WIFI:T:WPA;S:ssid;P:password;;"  (Android/iOS join-network format)
  * vcard -> a VCARD 3.0 block (adds the contact)
  * email -> "mailto:...?subject=...&body=..."
  * phone -> "tel:+1555..."

Validation lives here too, because a bad payload is the single most common way
a QR ends up unscannable or unsafe. URL validation in particular is security-
critical: for a dynamic redirect we will later send a scanner's browser to this
address, so we only ever allow http/https and explicitly reject dangerous
schemes like javascript: and data:.
"""
from urllib.parse import quote, urlparse

ALLOWED_URL_SCHEMES = {"http", "https"}

# Schemes we explicitly refuse for URL/redirect content. javascript: and data:
# can execute code or smuggle payloads; the rest have no place in a web redirect.
BLOCKED_URL_SCHEMES = {"javascript", "data", "vbscript", "file", "ftp"}

MAX_TEXT_LEN = 1200  # well within QR capacity at a readable size


class PayloadError(ValueError):
    """Raised when content is missing/invalid for its type. Routes turn this
    into a 422 with the message."""


def validate_destination_url(url: str) -> str:
    """Validate and normalise an http(s) URL. Used for URL QR content and for
    every dynamic-redirect destination.

    Raises PayloadError for anything that isn't a well-formed http/https URL.
    """
    if not url or not url.strip():
        raise PayloadError("URL is required")
    url = url.strip()

    parsed = urlparse(url)
    scheme = parsed.scheme.lower()

    if scheme in BLOCKED_URL_SCHEMES:
        raise PayloadError(f"URL scheme '{scheme}:' is not allowed")
    if scheme not in ALLOWED_URL_SCHEMES:
        raise PayloadError("URL must start with http:// or https://")
    if not parsed.netloc:
        raise PayloadError("URL must include a domain, e.g. https://example.com")
    return url


def _escape_wifi(value: str) -> str:
    r"""Escape the reserved characters in the WIFI: format ( \ ; , : " )."""
    for ch in ("\\", ";", ",", ":", '"'):
        value = value.replace(ch, "\\" + ch)
    return value


def _escape_vcard(value: str) -> str:
    r"""Escape reserved characters in vCard values ( \ ; , and newlines )."""
    value = value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
    return value.replace("\n", "\\n")


def _req(content: dict, key: str, label: str | None = None) -> str:
    val = str(content.get(key, "")).strip()
    if not val:
        raise PayloadError(f"{label or key} is required")
    return val


def build_payload(qr_type: str, content: dict) -> str:
    """Build the encoded string for a STATIC QR (or the underlying destination
    used to describe a dynamic one)."""
    if qr_type == "url":
        return validate_destination_url(str(content.get("url", "")))

    if qr_type == "text":
        text = _req(content, "text", "Text")
        if len(text) > MAX_TEXT_LEN:
            raise PayloadError(f"Text is too long (max {MAX_TEXT_LEN} characters)")
        return text

    if qr_type == "wifi":
        ssid = _req(content, "ssid", "Network name (SSID)")
        encryption = str(content.get("encryption", "WPA")).upper()
        if encryption not in {"WPA", "WEP", "NOPASS"}:
            raise PayloadError("Encryption must be WPA, WEP, or nopass")
        password = str(content.get("password", ""))
        if encryption != "NOPASS" and not password:
            raise PayloadError("Password is required for WPA/WEP networks")
        hidden = "true" if content.get("hidden") else "false"
        enc_field = "" if encryption == "NOPASS" else encryption
        pw_field = "" if encryption == "NOPASS" else _escape_wifi(password)
        return f"WIFI:T:{enc_field};S:{_escape_wifi(ssid)};P:{pw_field};H:{hidden};;"

    if qr_type == "vcard":
        name = _req(content, "name", "Name")
        lines = ["BEGIN:VCARD", "VERSION:3.0", f"N:{_escape_vcard(name)}", f"FN:{_escape_vcard(name)}"]
        if content.get("org"):
            lines.append(f"ORG:{_escape_vcard(str(content['org']))}")
        if content.get("phone"):
            lines.append(f"TEL;TYPE=CELL:{_escape_vcard(str(content['phone']))}")
        if content.get("email"):
            lines.append(f"EMAIL:{_escape_vcard(str(content['email']))}")
        if content.get("url"):
            # Contact website is validated the same way as any URL.
            lines.append(f"URL:{validate_destination_url(str(content['url']))}")
        if content.get("address"):
            lines.append(f"ADR;TYPE=HOME:;;{_escape_vcard(str(content['address']))}")
        lines.append("END:VCARD")
        return "\n".join(lines)

    if qr_type == "email":
        to = _req(content, "to", "Recipient email")
        params = []
        if content.get("subject"):
            params.append("subject=" + quote(str(content["subject"])))
        if content.get("body"):
            params.append("body=" + quote(str(content["body"])))
        query = ("?" + "&".join(params)) if params else ""
        return f"mailto:{to}{query}"

    if qr_type == "phone":
        phone = _req(content, "phone", "Phone number")
        # Keep digits, +, spaces, dashes and parentheses; reject anything else.
        cleaned = "".join(c for c in phone if c.isdigit() or c in "+- ()")
        if not any(c.isdigit() for c in cleaned):
            raise PayloadError("Phone number must contain digits")
        return f"tel:{cleaned.replace(' ', '')}"

    raise PayloadError(f"Unsupported QR type: {qr_type}")


def describe_destination(qr_type: str, content: dict, destination_url: str | None = None) -> str:
    """A short human-readable description of where a QR points, for the UI/history.
    For dynamic codes we show the editable destination_url."""
    if destination_url:
        return destination_url
    try:
        payload = build_payload(qr_type, content)
    except PayloadError:
        return "(incomplete)"
    return payload if len(payload) <= 80 else payload[:77] + "..."
