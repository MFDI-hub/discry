"""discord_client_scrapper: Scrape Discord web client bootstrap values."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("discord_client_scrapper")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0"

__all__ = ["__version__"]

# Re-export your public API from here (e.g. `from .core import Client`) and add
# each name to __all__. Avoid wildcard imports: they break static analysis.
