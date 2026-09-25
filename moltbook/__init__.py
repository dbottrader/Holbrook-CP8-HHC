"""Dependency-free client for the ASIN-HHC / CP8 Moltbook REST surface."""

from .client import DEFAULT_BASE_URL, ClientError, MoltbookClient

__all__ = ["DEFAULT_BASE_URL", "ClientError", "MoltbookClient"]
__version__ = "0.3.2"
