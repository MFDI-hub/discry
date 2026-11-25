"""Scraped Discord web-client surface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from .enums import AssetExtension, GatewayCompress, GatewayEncoding, StrEnum


class AssetDict(TypedDict):
    """
    JSON object for one content-hashed file.

    Attributes:
        name (str): File name without the hash or extension.
        hash (str): Content hash.
        ext (str): File extension.
    """

    name: str
    hash: str
    ext: str


class SurfaceDict(TypedDict):
    """
    JSON object stored for one channel in ``latest.json``.

    Attributes:
        build_number (int | None): Build number from the page or a script.
        version_hash (str | None): Build hash.
        build_id (str | None): Build id from the hash or the response header.
        built_at (str | None): Build timestamp from ``GLOBAL_ENV``.
        last_modified (str | None): ``Last-Modified`` response header.
        release_channel (str | None): Channel name from the page.
        api_version (int | None): REST API version.
        gateway_endpoint (str | None): Gateway websocket URL.
        api_endpoint (str | None): REST API host.
        remote_auth_endpoint (str | None): Remote auth gateway URL.
        cdn_host (str | None): CDN hostname.
        media_proxy_endpoint (str | None): Media proxy host.
        image_proxy_endpoints (str | None): Image proxy hosts.
        rtc_latency_endpoint (str | None): Voice latency probe URL.
        networking_endpoint (str | None): Router host.
        invite_host (str | None): Invite link host.
        gift_code_host (str | None): Gift link host.
        guild_template_host (str | None): Server template host.
        activity_application_host (str | None): Activity iframe host.
        assets (list[AssetDict]): Content-hashed files linked from the page.
        gateway_encoding (list[str]): Gateway encodings named in the client.
        gateway_compress (list[str]): Gateway compression modes named in the client.
        stripe_key (str | None): Stripe publishable key.
        adyen_key (str | None): Adyen client key.
        braintree_key (str | None): Braintree client key.
        capabilities (int | None): Capability mask the client sends.
        capability_values (list[int]): Every capability mask found beside that field.
        client_build_number (int | None): ``client_build_number`` from a script.
        scraped_at (str): ISO timestamp of the scrape. Empty when unknown.
    """

    build_number: int | None
    version_hash: str | None
    build_id: str | None
    built_at: str | None
    last_modified: str | None
    release_channel: str | None
    api_version: int | None
    gateway_endpoint: str | None
    api_endpoint: str | None
    remote_auth_endpoint: str | None
    cdn_host: str | None
    media_proxy_endpoint: str | None
    image_proxy_endpoints: str | None
    rtc_latency_endpoint: str | None
    networking_endpoint: str | None
    invite_host: str | None
    gift_code_host: str | None
    guild_template_host: str | None
    activity_application_host: str | None
    assets: list[AssetDict]
    gateway_encoding: list[str]
    gateway_compress: list[str]
    stripe_key: str | None
    adyen_key: str | None
    braintree_key: str | None
    capabilities: int | None
    capability_values: list[int]
    client_build_number: int | None
    scraped_at: str


class HistoryRow(TypedDict):
    """
    One appended row in ``history.json``.

    Attributes:
        channel (str): Channel name.
        build_number (int | None): Build number.
        version_hash (str | None): Build hash.
        build_id (str | None): Build id.
        capabilities (int | None): Capability mask.
        capability_values (list[int]): Capability masks found beside that field.
        client_build_number (int | None): ``client_build_number`` from a script.
        release_channel (str | None): Channel name from the page.
        built_at (str | None): Build timestamp.
        first_seen (str): ISO timestamp when this row was first recorded.
    """

    channel: str
    build_number: int | None
    version_hash: str | None
    build_id: str | None
    capabilities: int | None
    capability_values: list[int]
    client_build_number: int | None
    release_channel: str | None
    built_at: str | None
    first_seen: str


def _values(items: tuple[StrEnum, ...]) -> list[str]:
    """
    Return enum values as plain strings for JSON.

    Parameters:
        items (tuple[StrEnum, ...]): Enum members.

    Returns:
        list[str]: Member values, in the same order.
    """
    return [item.value for item in items]


@dataclass(frozen=True, slots=True)
class Asset:
    """
    One content-hashed file linked from the app HTML.

    Attributes:
        name (str): File name without the hash or extension.
        content_hash (str): Content hash.
        ext (AssetExtension): File extension.
    """

    name: str
    content_hash: str
    ext: AssetExtension

    def to_dict(self) -> AssetDict:
        """
        Return the JSON object for this file.

        Returns:
            AssetDict: Name, hash, and extension.
        """
        return {"name": self.name, "hash": self.content_hash, "ext": self.ext.value}


@dataclass(frozen=True, slots=True)
class ClientSurface:
    """
    Values stamped into one Discord web release.

    Missing values stay ``None`` or empty. A build that drops a field still
    produces a surface.

    Attributes:
        channel (str): Channel that was scraped.
        build_number (int | None): Build number from the page or a script.
        version_hash (str | None): Build hash.
        build_id (str | None): Build id from the hash or the response header.
        built_at (str | None): Build timestamp from ``GLOBAL_ENV``.
        last_modified (str | None): ``Last-Modified`` response header.
        release_channel (str | None): Channel name from the page.
        api_version (int | None): REST API version.
        gateway_endpoint (str | None): Gateway websocket URL.
        api_endpoint (str | None): REST API host.
        remote_auth_endpoint (str | None): Remote auth gateway URL.
        cdn_host (str | None): CDN hostname.
        media_proxy_endpoint (str | None): Media proxy host.
        image_proxy_endpoints (str | None): Image proxy hosts.
        rtc_latency_endpoint (str | None): Voice latency probe URL.
        networking_endpoint (str | None): Router host.
        invite_host (str | None): Invite link host.
        gift_code_host (str | None): Gift link host.
        guild_template_host (str | None): Server template host.
        activity_application_host (str | None): Activity iframe host.
        assets (tuple[Asset, ...]): Content-hashed files linked from the page.
        gateway_encoding (tuple[GatewayEncoding, ...]): Gateway encodings.
        gateway_compress (tuple[GatewayCompress, ...]): Gateway compression modes.
        stripe_key (str | None): Stripe publishable key.
        adyen_key (str | None): Adyen client key.
        braintree_key (str | None): Braintree client key.
        capabilities (int | None): Capability mask the client sends.
        capability_values (tuple[int, ...]): Every capability mask found beside that field.
        client_build_number (int | None): ``client_build_number`` from a script.
        scraped_at (str): ISO timestamp of the scrape. Empty when unknown.
    """

    channel: str
    build_number: int | None = None
    version_hash: str | None = None
    build_id: str | None = None
    built_at: str | None = None
    last_modified: str | None = None
    release_channel: str | None = None
    api_version: int | None = None
    gateway_endpoint: str | None = None
    api_endpoint: str | None = None
    remote_auth_endpoint: str | None = None
    cdn_host: str | None = None
    media_proxy_endpoint: str | None = None
    image_proxy_endpoints: str | None = None
    rtc_latency_endpoint: str | None = None
    networking_endpoint: str | None = None
    invite_host: str | None = None
    gift_code_host: str | None = None
    guild_template_host: str | None = None
    activity_application_host: str | None = None
    assets: tuple[Asset, ...] = ()
    gateway_encoding: tuple[GatewayEncoding, ...] = ()
    gateway_compress: tuple[GatewayCompress, ...] = ()
    stripe_key: str | None = None
    adyen_key: str | None = None
    braintree_key: str | None = None
    capabilities: int | None = None
    capability_values: tuple[int, ...] = ()
    client_build_number: int | None = None
    scraped_at: str = ""

    def to_dict(self) -> SurfaceDict:
        """
        Return the JSON object stored for this channel.

        Returns:
            SurfaceDict: Surface fields with enums written as their values.
        """
        return {
            "build_number": self.build_number,
            "version_hash": self.version_hash,
            "build_id": self.build_id,
            "built_at": self.built_at,
            "last_modified": self.last_modified,
            "release_channel": self.release_channel,
            "api_version": self.api_version,
            "gateway_endpoint": self.gateway_endpoint,
            "api_endpoint": self.api_endpoint,
            "remote_auth_endpoint": self.remote_auth_endpoint,
            "cdn_host": self.cdn_host,
            "media_proxy_endpoint": self.media_proxy_endpoint,
            "image_proxy_endpoints": self.image_proxy_endpoints,
            "rtc_latency_endpoint": self.rtc_latency_endpoint,
            "networking_endpoint": self.networking_endpoint,
            "invite_host": self.invite_host,
            "gift_code_host": self.gift_code_host,
            "guild_template_host": self.guild_template_host,
            "activity_application_host": self.activity_application_host,
            "assets": [asset.to_dict() for asset in self.assets],
            "gateway_encoding": _values(self.gateway_encoding),
            "gateway_compress": _values(self.gateway_compress),
            "stripe_key": self.stripe_key,
            "adyen_key": self.adyen_key,
            "braintree_key": self.braintree_key,
            "capabilities": self.capabilities,
            "capability_values": list(self.capability_values),
            "client_build_number": self.client_build_number,
            "scraped_at": self.scraped_at,
        }

    def history_row(self, first_seen: str) -> HistoryRow:
        """
        Return the history row recorded the first time this surface is seen.

        Parameters:
            first_seen (str): ISO timestamp stored on the row.

        Returns:
            HistoryRow: Identity fields plus ``first_seen``.
        """
        return {
            "channel": self.channel,
            "build_number": self.build_number,
            "version_hash": self.version_hash,
            "build_id": self.build_id,
            "capabilities": self.capabilities,
            "capability_values": list(self.capability_values),
            "client_build_number": self.client_build_number,
            "release_channel": self.release_channel,
            "built_at": self.built_at,
            "first_seen": first_seen,
        }
