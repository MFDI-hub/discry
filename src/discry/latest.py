"""Read a published ``latest.json`` without scraping Discord."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, TypeVar

import orjson

from .config import DEFAULT_LATEST_URL as DEFAULT_LATEST_URL, Settings
from .enums import AssetExtension, GatewayCompress, GatewayEncoding, StrEnum
from .errors import DiscryError
from .http_client import request_get
from .models import Asset, ClientSurface, slotted

logger = logging.getLogger(__name__)

_BLOB_URL = re.compile(
    r"^https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/blob/(?P<ref>[^/]+)/(?P<path>.+)$"
)
_EnumMember = TypeVar("_EnumMember", bound=StrEnum)


class LatestFetchError(DiscryError):
    """
    Raised when latest.json cannot be fetched or parsed.
    """

    __slots__ = ()


@slotted
@dataclass(frozen=True)
class LatestSurfaces:
    """
    Channels from one published ``latest.json``.

    Attributes:
        updated_at (str): Timestamp on the snapshot.
        channels (dict[str, ClientSurface]): Surfaces keyed by channel name.
        source_url (str): URL the snapshot was read from.
    """

    updated_at: str
    channels: dict[str, ClientSurface]
    source_url: str

    def __getitem__(self, channel: str) -> ClientSurface:
        """
        Return the surface for one channel.

        Parameters:
            channel (str): Channel name.

        Returns:
            ClientSurface: Surface stored under that name.

        Raises:
            KeyError: ``channel`` is absent. The message lists the names that
                are present.
        """
        try:
            return self.channels[channel]
        except KeyError as exc:
            available = ", ".join(sorted(self.channels)) or "(none)"
            raise KeyError(
                f"Channel {channel!r} not in latest.json. Available: {available}"
            ) from exc


def to_raw_github_url(url: str) -> str:
    """
    Turn a GitHub blob page URL into a raw file URL.

    Parameters:
        url (str): Blob URL or any other URL.

    Returns:
        str: Raw GitHub URL when ``url`` is a blob page, otherwise ``url``.
    """
    match = _BLOB_URL.match(url.strip())
    if not match:
        return url
    return (
        "https://raw.githubusercontent.com/"
        f"{match.group('owner')}/{match.group('repo')}/{match.group('ref')}/{match.group('path')}"
    )


def _optional_int(payload: dict[str, Any], key: str) -> int | None:
    """
    Return an integer field, or None when it is missing or blank.

    Parameters:
        payload (dict[str, Any]): Channel object.
        key (str): Field name.

    Returns:
        int | None: Parsed integer, or None.
    """
    value = payload.get(key)
    if value is None or value == "":
        return None
    return int(value)


def _optional_str(payload: dict[str, Any], key: str) -> str | None:
    """
    Return a stripped string field, or None when it is missing or blank.

    Parameters:
        payload (dict[str, Any]): Channel object.
        key (str): Field name.

    Returns:
        str | None: Stripped text, or None.
    """
    value = payload.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _assets(payload: dict[str, Any]) -> tuple[Asset, ...]:
    """
    Return content-hashed files from a channel object.

    Parameters:
        payload (dict[str, Any]): Channel object.

    Returns:
        tuple[Asset, ...]: Files with a name, hash, and known extension.
        Entries that are not objects, or that omit a field, are skipped.
    """
    raw = payload.get("assets") or []
    if not isinstance(raw, list):
        return ()
    assets: list[Asset] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        content_hash = item.get("hash")
        ext = item.get("ext")
        if not name or not content_hash or not ext:
            continue
        assets.append(
            Asset(
                name=str(name),
                content_hash=str(content_hash),
                ext=AssetExtension(str(ext).lower()),
            )
        )
    return tuple(assets)


def _enum_members(
    payload: dict[str, Any],
    key: str,
    enum_type: type[_EnumMember],
) -> tuple[_EnumMember, ...]:
    """
    Return enum members stored as one string or a list of strings.

    Parameters:
        payload (dict[str, Any]): Channel object.
        key (str): Field name.
        enum_type (type[_EnumMember]): Enum the values must belong to.

    Returns:
        tuple[_EnumMember, ...]: Members in file order. Empty when the field
        is missing or not a string or list.
    """
    raw = payload.get(key) or []
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, list):
        return ()
    return tuple(enum_type(str(item).lower()) for item in raw if item)


def _ints(payload: dict[str, Any], key: str) -> tuple[int, ...]:
    """
    Return an integer list field.

    Parameters:
        payload (dict[str, Any]): Channel object.
        key (str): Field name.

    Returns:
        tuple[int, ...]: Integers, or an empty tuple when the field is missing
        or not a list.
    """
    raw = payload.get(key) or []
    if not isinstance(raw, list):
        return ()
    return tuple(int(item) for item in raw)


def surface_from_payload(channel: str, payload: Any) -> ClientSurface:
    """
    Build a surface from one channel object in ``latest.json``.

    Parameters:
        channel (str): Channel name.
        payload (Any): JSON value stored for that channel.

    Returns:
        ClientSurface: Parsed surface.

    Raises:
        LatestFetchError: ``payload`` is not an object, or a field has the
            wrong type or an unknown enum value.
    """
    if not isinstance(payload, dict):
        raise LatestFetchError(f"Channel {channel!r} must be a JSON object")
    try:
        return ClientSurface(
            channel=channel,
            build_number=_optional_int(payload, "build_number"),
            version_hash=_optional_str(payload, "version_hash"),
            build_id=_optional_str(payload, "build_id"),
            built_at=_optional_str(payload, "built_at"),
            last_modified=_optional_str(payload, "last_modified"),
            release_channel=_optional_str(payload, "release_channel"),
            api_version=_optional_int(payload, "api_version"),
            gateway_endpoint=_optional_str(payload, "gateway_endpoint"),
            api_endpoint=_optional_str(payload, "api_endpoint"),
            remote_auth_endpoint=_optional_str(payload, "remote_auth_endpoint"),
            cdn_host=_optional_str(payload, "cdn_host"),
            media_proxy_endpoint=_optional_str(payload, "media_proxy_endpoint"),
            image_proxy_endpoints=_optional_str(payload, "image_proxy_endpoints"),
            rtc_latency_endpoint=_optional_str(payload, "rtc_latency_endpoint"),
            networking_endpoint=_optional_str(payload, "networking_endpoint"),
            invite_host=_optional_str(payload, "invite_host"),
            gift_code_host=_optional_str(payload, "gift_code_host"),
            guild_template_host=_optional_str(payload, "guild_template_host"),
            activity_application_host=_optional_str(payload, "activity_application_host"),
            assets=_assets(payload),
            gateway_encoding=_enum_members(payload, "gateway_encoding", GatewayEncoding),
            gateway_compress=_enum_members(payload, "gateway_compress", GatewayCompress),
            stripe_key=_optional_str(payload, "stripe_key"),
            adyen_key=_optional_str(payload, "adyen_key"),
            braintree_key=_optional_str(payload, "braintree_key"),
            capabilities=_optional_int(payload, "capabilities"),
            capability_values=_ints(payload, "capability_values"),
            client_build_number=_optional_int(payload, "client_build_number"),
            scraped_at=str(payload.get("scraped_at") or ""),
        )
    except (TypeError, ValueError) as exc:
        raise LatestFetchError(f"Channel {channel!r} is missing or invalid: {exc}") from exc


def parse_latest(payload: Any, source_url: str) -> LatestSurfaces:
    """
    Parse a ``latest.json`` document.

    Parameters:
        payload (Any): Decoded JSON.
        source_url (str): URL stored on the result.

    Returns:
        LatestSurfaces: Snapshot channels.

    Raises:
        LatestFetchError: The document is missing ``updated_at`` or a non-empty
            ``channels`` object, or a channel object is invalid.
    """
    if not isinstance(payload, dict):
        raise LatestFetchError("latest.json must be a JSON object")
    channels_raw = payload.get("channels")
    if not isinstance(channels_raw, dict) or not channels_raw:
        raise LatestFetchError("latest.json is missing a channels object")
    updated_at = payload.get("updated_at")
    if updated_at is None:
        raise LatestFetchError("latest.json is missing updated_at")
    channels = {
        str(name): surface_from_payload(str(name), body) for name, body in channels_raw.items()
    }
    return LatestSurfaces(updated_at=str(updated_at), channels=channels, source_url=source_url)


def fetch_latest(
    url: str | None = None,
    settings: Settings | None = None,
) -> LatestSurfaces:
    """
    Fetch the published latest.json for this package.

    Parameters:
        url (str | None): Snapshot URL. None uses ``settings.latest_url``.
            GitHub blob URLs are converted to raw.
        settings (Settings | None): HTTP settings. Defaults to ``Settings()``.

    Returns:
        LatestSurfaces: Parsed snapshot.

    Raises:
        LatestFetchError: The response is not successful or is not the
            expected JSON document.
    """
    settings = settings or Settings()
    source_url = to_raw_github_url(url or settings.latest_url)
    logger.info("Fetching latest surfaces from %s", source_url)
    response = request_get(source_url, settings)
    if not response.ok:
        raise LatestFetchError(f"Failed to fetch {source_url}: HTTP {response.status_code}")
    try:
        payload = orjson.loads(response.content)
    except orjson.JSONDecodeError as exc:
        raise LatestFetchError(f"Response from {source_url} is not valid JSON") from exc
    return parse_latest(payload, source_url)


def fetch_latest_channel(
    channel: str,
    url: str | None = None,
    settings: Settings | None = None,
) -> ClientSurface:
    """
    Fetch one channel from the published latest.json.

    Parameters:
        channel (str): Channel name.
        url (str | None): Snapshot URL. None uses ``settings.latest_url``.
            GitHub blob URLs are converted to raw.
        settings (Settings | None): HTTP settings. Defaults to ``Settings()``.

    Returns:
        ClientSurface: Surface for ``channel``.

    Raises:
        LatestFetchError: The snapshot cannot be fetched or parsed.
        KeyError: ``channel`` is not in the snapshot.
    """
    return fetch_latest(url=url, settings=settings)[channel]
