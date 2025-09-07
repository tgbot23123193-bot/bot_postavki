"""API package initialization."""

from .wb_client import WBAPIClient, WBAPIError
from .schemas import *

__all__ = [
    "WBAPIClient",
    "WBAPIError",
]
