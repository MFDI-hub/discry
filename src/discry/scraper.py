"""Fetch Discord's public app page and the one or two scripts that carry identify data."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import TYPE_CHECKING

from .client_code import ChannelCapture
from .config import Settings, resolve_timezone
from .errors import DiscryError
from .extract import assemble_surface, partition_scripts, script_paths
from .http_client import request_get

if TYPE_CHECKING:
    from .models import ClientSurface

logger = logging.getLogger(__name__)


async def _in_thread(func, *args):
    """
    Run a blocking function on a worker thread.

    Parameters:
        func (object): Callable to run.
        *args (object): Positional arguments for ``func``.

    Returns:
        object: Whatever ``func`` returns.
    """
    return await asyncio.to_thread(func, *args)


class SurfaceNotFoundError(DiscryError):
    """
    Raised when a channel page has none of the build identity fields.
    """

    __slots__ = ()


def _field_present(surface: ClientSurface, name: str) -> bool:
    """
    Return whether one surface field has a value.

    Parameters:
        surface (ClientSurface): Surface to inspect.
        name (str): Field name.

    Returns:
        bool: True when the value is not None. Empty sequences are absent.
    """
    value = getattr(surface, name)
    if isinstance(value, (tuple, list, dict)):
        return len(value) > 0
    return value is not None


def _fields_match(surface: ClientSurface, names: tuple[str, ...], mode: str) -> bool:
    """
    Return whether the named fields are present.

    Parameters:
        surface (ClientSurface): Surface to inspect.
        names (tuple[str, ...]): Field names.
        mode (str): ``any`` or ``all``.

    Returns:
        bool: True when the match mode is satisfied. An empty name list matches.
    """
    if not names:
        return True
    flags = [_field_present(surface, name) for name in names]
    if mode == "any":
        return any(flags)
    return all(flags)


def _asset_base(settings: Settings, domain: str) -> str:
    """
    Return the origin used to download asset files.

    Parameters:
        settings (Settings): Active settings.
        domain (str): Channel hostname.

    Returns:
        str: Configured asset base, or the channel scheme and host.
    """
    if settings.asset_base_url:
        return settings.asset_base_url.rstrip("/")
    return f"{settings.url_scheme}://{domain}"


def _download_text(url: str, settings: Settings) -> str:
    """
    Download one URL and return its body.

    Parameters:
        url (str): Absolute URL.
        settings (Settings): Active settings.

    Returns:
        str: Response body. Empty when the body is missing.

    Raises:
        RuntimeError: The response status is not successful.
    """
    response = request_get(url, settings)
    if not response.ok:
        raise RuntimeError(f"Failed to fetch {url}: HTTP {response.status_code}")
    return str(response.text or "")


async def _download_text_async(url: str, settings: Settings, semaphore: asyncio.Semaphore) -> str:
    """
    Download one URL on a worker thread, bounded by ``semaphore``.

    Parameters:
        url (str): Absolute URL.
        settings (Settings): Active settings.
        semaphore (asyncio.Semaphore): Parallel download limit.

    Returns:
        str: Response body.
    """
    async with semaphore:
        return await _in_thread(_download_text, url, settings)


async def _download_paths(paths: list[str], settings: Settings, base: str) -> dict[str, str]:
    """
    Download script paths. A failed path is logged and omitted.

    Parameters:
        paths (list[str]): Script paths, each starting with ``/``.
        settings (Settings): Active settings.
        base (str): Origin prepended to each path.

    Returns:
        dict[str, str]: Path to body, for the downloads that succeeded.

    Raises:
        ValueError: A batch and its results differ in length.
    """
    found: dict[str, str] = {}
    if not paths:
        return found
    semaphore = asyncio.Semaphore(settings.download_concurrency)
    index = 0
    while index < len(paths):
        batch = paths[index : index + settings.download_concurrency]
        index += len(batch)
        results = await asyncio.gather(
            *[_download_text_async(f"{base}{path}", settings, semaphore) for path in batch],
            return_exceptions=True,
        )
        if len(batch) != len(results):
            raise ValueError("download batch and results differ in length")
        for path, result in zip(batch, results, strict=True):
            if isinstance(result, BaseException):
                logger.warning("Skipping %s: %s", path, result)
                continue
            found[path] = result
    return found


def _ordered_scripts(
    html: str, downloaded: dict[str, str], settings: Settings
) -> tuple[tuple[str, str], ...]:
    """
    Return downloaded scripts in the order the page links them.

    Parameters:
        html (str): App page HTML.
        downloaded (dict[str, str]): Script path to body.
        settings (Settings): Asset prefix and extensions.

    Returns:
        tuple[tuple[str, str], ...]: Path and body pairs.
    """
    return tuple(
        (path, downloaded[path]) for path in script_paths(html, settings) if path in downloaded
    )


async def scrape_channel(
    channel: str,
    settings: Settings | None = None,
    scraped_at: datetime | None = None,
) -> ClientSurface:
    """
    Scrape one release channel.

    Optional fields may be missing. The returned surface still has a build
    number, version hash, or build id. When ``save_client`` is true, the page
    scripts are downloaded even after the surface is complete, so the caller
    can store them.

    Parameters:
        channel (str): Channel name. Must have a domain in ``settings``.
        settings (Settings | None): Active settings. Defaults to ``Settings()``.
        scraped_at (datetime | None): Timestamp stored on the surface. Defaults
            to the current UTC time.

    Returns:
        ClientSurface: Values read from the app page and, when needed, scripts.

    Raises:
        ValueError: ``channel`` has no configured domain.
        SurfaceNotFoundError: The page could not be fetched, or it has no
            build identity.
    """
    return (await capture_channel(channel, settings=settings, scraped_at=scraped_at)).surface


async def capture_channel(
    channel: str,
    settings: Settings | None = None,
    scraped_at: datetime | None = None,
) -> ChannelCapture:
    """
    Scrape one channel and keep the page and script bodies.

    Parameters:
        channel (str): Channel name. Must have a domain in ``settings``.
        settings (Settings | None): Active settings. Defaults to ``Settings()``.
        scraped_at (datetime | None): Timestamp stored on the surface. Defaults
            to the current UTC time.

    Returns:
        ChannelCapture: Surface, app HTML, and the scripts that downloaded.

    Raises:
        ValueError: ``channel`` has no configured domain.
        SurfaceNotFoundError: The page could not be fetched, or it has no
            build identity.
    """
    settings = settings or Settings()
    if channel not in settings.domains:
        raise ValueError(f"Unsupported channel: {channel}")

    scraped_at = scraped_at or datetime.now(resolve_timezone(settings.timezone))
    domain = settings.domains[channel]
    app_path = settings.app_path if settings.app_path.startswith("/") else f"/{settings.app_path}"
    app_url = f"{settings.url_scheme}://{domain}{app_path}"
    logger.info("Fetching %s from %s (impersonate=%s)", channel, app_url, settings.impersonate)

    response = await _in_thread(request_get, app_url, settings)
    if not response.ok:
        raise SurfaceNotFoundError(f"Failed to fetch {app_url}: HTTP {response.status_code}")

    html = str(response.text or "")
    headers = {str(key): str(value) for key, value in dict(response.headers).items()}
    surface = assemble_surface(
        channel=channel,
        html=html,
        headers=headers,
        scraped_at=scraped_at,
        settings=settings,
    )
    downloaded: dict[str, str] = {}
    attempted: set[str] = set()
    base = _asset_base(settings, domain)
    if not (
        _fields_match(surface, settings.identity_fields, settings.identity_match)
        and _fields_match(surface, settings.skip_script_fields, "all")
    ):
        priority, rest = partition_scripts(script_paths(html, settings), settings)
        selected = list(priority)
        if not _fields_match(surface, settings.rest_script_fields, "all"):
            selected.extend(rest)
        selected = selected[: settings.max_files]
        bodies: list[str] = []
        inspected = 0
        index = 0
        while selected and index < len(selected) and inspected < settings.max_files:
            if _fields_match(surface, settings.stop_fields, "all") and (
                _fields_match(surface, settings.stop_early_fields, "all")
                or inspected >= len(priority)
            ):
                break
            batch = selected[index : index + settings.download_concurrency]
            index += len(batch)
            inspected += len(batch)
            attempted.update(batch)
            found = await _download_paths(batch, settings, base)
            for path in batch:
                body = found.get(path)
                if body is None:
                    continue
                downloaded[path] = body
                bodies.append(body)
            surface = assemble_surface(
                channel=channel,
                html=html,
                scripts=bodies,
                headers=headers,
                scraped_at=scraped_at,
                settings=settings,
            )

    surface = _require_identity(surface, channel, settings)
    if settings.save_client:
        pending_priority, pending_rest = partition_scripts(
            [path for path in script_paths(html, settings) if path not in attempted],
            settings,
        )
        room = settings.max_files - len(attempted)
        if room > 0:
            extra = [*pending_priority, *pending_rest][:room]
            attempted.update(extra)
            downloaded.update(await _download_paths(extra, settings, base))
    return ChannelCapture(
        surface=surface,
        page=html,
        scripts=_ordered_scripts(html, downloaded, settings),
    )


def _require_identity(surface: ClientSurface, channel: str, settings: Settings) -> ClientSurface:
    """
    Return ``surface`` when it has a build identity.

    Parameters:
        surface (ClientSurface): Surface assembled so far.
        channel (str): Channel name, used in the error and the warning.
        settings (Settings): Identity fields and match mode.

    Returns:
        ClientSurface: The same surface.

    Raises:
        SurfaceNotFoundError: The configured identity fields were not found.
    """
    if _fields_match(surface, settings.identity_fields, settings.identity_match):
        if surface.capabilities is None:
            logger.warning("%s page had no capabilities mask", channel)
        return surface
    raise SurfaceNotFoundError(
        f"Could not find a build number or build hash for {channel}. "
        "The app page did not look like the Discord client."
    )


async def scrape_channels(
    settings: Settings | None = None,
    channels: tuple[str, ...] | None = None,
    scraped_at: datetime | None = None,
) -> list[ClientSurface]:
    """
    Scrape each channel.

    One failure fails the run after the others are attempted.

    Parameters:
        settings (Settings | None): Active settings. Defaults to ``Settings()``.
        channels (tuple[str, ...] | None): Channels to scrape. Defaults to
            ``settings.channels``.
        scraped_at (datetime | None): Timestamp stored on every surface.

    Returns:
        list[ClientSurface]: One surface per channel, in request order.

    Raises:
        SurfaceNotFoundError: One or more channels failed. The message lists
            each failure.
    """
    return [
        item.surface
        for item in await capture_channels(
            settings=settings, channels=channels, scraped_at=scraped_at
        )
    ]


async def capture_channels(
    settings: Settings | None = None,
    channels: tuple[str, ...] | None = None,
    scraped_at: datetime | None = None,
) -> list[ChannelCapture]:
    """
    Scrape each channel and keep the page and script bodies.

    One failure fails the run after the others are attempted.

    Parameters:
        settings (Settings | None): Active settings. Defaults to ``Settings()``.
        channels (tuple[str, ...] | None): Channels to scrape. Defaults to
            ``settings.channels``.
        scraped_at (datetime | None): Timestamp stored on every surface.

    Returns:
        list[ChannelCapture]: One capture per channel, in request order.

    Raises:
        SurfaceNotFoundError: One or more channels failed. The message lists
            each failure.
    """
    settings = settings or Settings()
    channels = channels or settings.channels
    scraped_at = scraped_at or datetime.now(resolve_timezone(settings.timezone))
    found: list[ChannelCapture] = []
    errors: list[str] = []

    async def _one(channel: str) -> ChannelCapture | Exception:
        try:
            return await capture_channel(channel, settings=settings, scraped_at=scraped_at)
        except Exception as exc:
            logger.exception("Failed to scrape %s", channel)
            return exc

    if settings.channel_concurrency <= 1:
        results: list[ChannelCapture | Exception] = []
        for channel in channels:
            results.append(await _one(channel))
    else:
        semaphore = asyncio.Semaphore(settings.channel_concurrency)

        async def _limited(channel: str) -> ChannelCapture | Exception:
            async with semaphore:
                return await _one(channel)

        results = list(await asyncio.gather(*(_limited(channel) for channel in channels)))

    for channel, result in zip(channels, results, strict=True):
        if isinstance(result, Exception):
            errors.append(f"{channel}: {result}")
        else:
            found.append(result)
    if errors and not (settings.continue_on_error and found):
        raise SurfaceNotFoundError(f"Failed to scrape one or more channels: {'; '.join(errors)}")
    return found
