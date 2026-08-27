"""Minimal, explicit logging setup.

We log startup, errors, and a few important operations (QR created, scan
recorded). We deliberately never log passwords, tokens, the JWT secret, or
raw request bodies, so log files can't leak credentials.
"""
import logging


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
