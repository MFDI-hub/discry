"""Save the app page and the scripts it links, and replace them when they change."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Settings
    from .models import ClientSurface

logger = logging.getLogger(__name__)

_PAGE_NAME = "app.html"
_HASHED_NAME = re.compile(r"^(?P<name>.+)\.(?P<hash>[0-9a-fA-F]+)\.(?P<ext>[^.]+)$")


@dataclass(frozen=True, slots=True)
class ChannelCapture:
    """
    One channel's surface plus the page and scripts that produced it.

    Attributes:
        surface (ClientSurface): Values read from the page and scripts.
        page (str): App HTML.
        scripts (tuple[tuple[str, str], ...]): Script path and body, in page
            order. Only scripts that downloaded successfully are included.
    """

    surface: ClientSurface
    page: str
    scripts: tuple[tuple[str, str], ...] = ()


def client_root(data_dir: Path, settings: Settings) -> Path:
    """
    Return the directory that holds the saved client code.

    Parameters:
        data_dir (Path): Directory used when ``client_dir`` is unset.
        settings (Settings): Active settings.

    Returns:
        Path: ``client_dir``, or ``data_dir / client``.
    """
    if settings.client_dir:
        return Path(settings.client_dir)
    return data_dir / "client"


def logical_script_name(path: str, settings: Settings) -> str:
    """
    Return a stable file name for one asset script.

    ``web.<hash>.js`` is stored as ``web.js``, so a new build replaces the
    same path. A hash outside the configured length stays in the name.

    Parameters:
        path (str): Script path from the app page.
        settings (Settings): Accepted asset-hash length.

    Returns:
        str: File name with no directory.
    """
    base = path.replace("\\", "/").rsplit("/", 1)[-1]
    if base in {"", ".", ".."}:
        return "script.js"
    match = _HASHED_NAME.fullmatch(base)
    if match is None:
        return base
    digest = match.group("hash")
    if not settings.asset_hash_min_length <= len(digest) <= settings.asset_hash_max_length:
        return base
    return f"{match.group('name')}.{match.group('ext')}"


def _channel_dir(root: Path, channel: str) -> Path:
    """
    Return the directory for one channel.

    Parameters:
        root (Path): Client-code root.
        channel (str): Channel name.

    Returns:
        Path: ``root / channel``.

    Raises:
        ValueError: ``channel`` is not a single path segment.
    """
    if channel in {"", ".", ".."} or "/" in channel or "\\" in channel:
        raise ValueError(f"Channel name cannot be a path: {channel!r}")
    return root / channel


def _write_if_changed(path: Path, payload: bytes) -> bool:
    """
    Write ``payload`` when the file is missing or different.

    Parameters:
        path (Path): Destination file.
        payload (bytes): New contents.

    Returns:
        bool: True when the file was written.
    """
    if path.is_file() and path.read_bytes() == payload:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return True


def _channel_files(capture: ChannelCapture, settings: Settings) -> dict[str, bytes]:
    """
    Return the file names and bodies for one channel.

    Parameters:
        capture (ChannelCapture): Page and scripts.
        settings (Settings): Hash length used to strip content hashes.

    Returns:
        dict[str, bytes]: File name to body. The page is ``app.html``.
    """
    files = {_PAGE_NAME: capture.page.encode()}
    for path, body in capture.scripts:
        name = logical_script_name(path, settings)
        payload = body.encode()
        if name in files and files[name] != payload:
            name = path.replace("\\", "/").rsplit("/", 1)[-1] or name
        files[name] = payload
    return files


def write_client_files(
    data_dir: Path,
    captures: list[ChannelCapture],
    settings: Settings,
) -> list[Path]:
    """
    Write each channel's page and scripts, and drop files that are gone.

    A file whose bytes did not change is left untouched. A script Discord no
    longer links is deleted. ``save_client = false`` writes nothing.

    Parameters:
        data_dir (Path): Directory used when ``client_dir`` is unset.
        captures (list[ChannelCapture]): Channels scraped in this run.
        settings (Settings): Output switch and paths.

    Returns:
        list[Path]: Files written or deleted.

    Raises:
        ValueError: A channel name is not a single path segment.
    """
    if not settings.save_client:
        return []
    root = client_root(data_dir, settings)
    changed: list[Path] = []
    for capture in captures:
        directory = _channel_dir(root, capture.surface.channel)
        files = _channel_files(capture, settings)
        directory.mkdir(parents=True, exist_ok=True)
        for name, payload in files.items():
            path = directory / name
            if _write_if_changed(path, payload):
                logger.info("Updated %s", path)
                changed.append(path)
        for existing in directory.iterdir():
            if existing.is_file() and existing.name not in files:
                existing.unlink()
                logger.info("Removed %s", existing)
                changed.append(existing)
    return changed
