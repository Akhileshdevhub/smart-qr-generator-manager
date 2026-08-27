"""A single shared rate limiter (slowapi) used to protect abuse-prone endpoints:
login, registration, QR preview rendering, and the public redirect.

Keyed by client IP. In production behind a proxy you would configure the proxy
to set X-Forwarded-For and trust it; that nuance is noted in docs/security.md.
Limits are intentionally generous so normal use is never blocked.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address, default_limits=[])
