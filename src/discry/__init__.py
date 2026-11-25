"""Scrape the public Discord web client's per-release bootstrap values."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from .cli import main
from .enums import AssetExtension, ExitCode, GatewayCompress, GatewayEncoding, ReleaseChannel
from .errors import DiscryError
from .latest import LatestFetchError, LatestSurfaces, fetch_latest, fetch_latest_channel
from .models import ClientSurface
from .scraper import SurfaceNotFoundError, scrape_channel, scrape_channels

try:
    __version__ = version("discry")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

__all__ = [
    "AssetExtension",
    "ClientSurface",
    "DiscryError",
    "ExitCode",
    "GatewayCompress",
    "GatewayEncoding",
    "LatestFetchError",
    "LatestSurfaces",
    "ReleaseChannel",
    "SurfaceNotFoundError",
    "__version__",
    "fetch_latest",
    "fetch_latest_channel",
    "main",
    "scrape_channel",
    "scrape_channels",
]
