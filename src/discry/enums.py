"""Closed sets used by the scraper, the snapshot files, and the command line."""

from __future__ import annotations

from enum import Enum, IntEnum, unique


class StrEnum(str, Enum):
    """
    Enum whose members are also strings.

    The standard library class arrived in Python 3.11. This one keeps the same
    behavior on Python 3.10. Members compare equal to their string values.

    Attributes:
        value (str): Text stored on the member.
    """

    def __new__(cls, value: str) -> StrEnum:
        """
        Create a member that is also a string.

        Parameters:
            value (str): Member text.

        Returns:
            StrEnum: The new member.
        """
        member = str.__new__(cls, value)
        member._value_ = value
        return member

    def __str__(self) -> str:
        """
        Return the member text.

        Returns:
            str: The value passed when the member was defined.
        """
        return str(self.value)

    def __format__(self, format_spec: str) -> str:
        """
        Format the member as its text.

        Parameters:
            format_spec (str): Format spec applied to the value.

        Returns:
            str: Formatted member text.
        """
        return format(self.value, format_spec)

    __slots__ = ()


@unique
class ReleaseChannel(StrEnum):
    """
    Built-in Discord web release channels.

    A config file may name further channels when each one has a domain.
    Members compare equal to their string values.

    Attributes:
        STABLE (str): Production client.
        PTB (str): Public test build.
        CANARY (str): Canary client.
    """

    __slots__ = ()

    STABLE = "stable"
    PTB = "ptb"
    CANARY = "canary"


@unique
class GatewayEncoding(StrEnum):
    """
    Gateway payload encodings the web client offers.

    Attributes:
        JSON (str): JSON text frames.
        ETF (str): Erlang term format frames.
    """

    __slots__ = ()

    JSON = "json"
    ETF = "etf"


@unique
class GatewayCompress(StrEnum):
    """
    Gateway compression modes named in the web client.

    Attributes:
        ZSTD_STREAM (str): zstd streaming compression.
        ZLIB_STREAM (str): zlib streaming compression.
    """

    __slots__ = ()

    ZSTD_STREAM = "zstd-stream"
    ZLIB_STREAM = "zlib-stream"


@unique
class AssetExtension(StrEnum):
    """
    Content-hashed file extensions linked from the app page.

    Attributes:
        JS (str): JavaScript bundle.
        CSS (str): Stylesheet.
        MJS (str): ES module bundle.
    """

    __slots__ = ()

    JS = "js"
    CSS = "css"
    MJS = "mjs"


@unique
class EnvKey(StrEnum):
    """
    Canonical ``GLOBAL_ENV`` names.

    Lookups also accept camelCase and lower_snake spellings of each name.

    Attributes:
        BUILD_NUMBER (str): Client build number.
        VERSION_HASH (str): Build hash stamped into the page.
        BUILT_AT (str): Build timestamp.
        RELEASE_CHANNEL (str): Channel name baked into the page.
        API_VERSION (str): REST API version.
        GATEWAY_ENDPOINT (str): Gateway websocket URL.
        API_ENDPOINT (str): REST API host.
        REMOTE_AUTH_ENDPOINT (str): Remote auth gateway URL.
        CDN_HOST (str): CDN hostname.
        MEDIA_PROXY_ENDPOINT (str): Media proxy host.
        IMAGE_PROXY_ENDPOINTS (str): Image proxy hosts.
        RTC_LATENCY_ENDPOINT (str): Voice latency probe URL.
        NETWORKING_ENDPOINT (str): Router host.
        INVITE_HOST (str): Invite link host.
        GIFT_CODE_HOST (str): Gift link host.
        GUILD_TEMPLATE_HOST (str): Server template host.
        ACTIVITY_APPLICATION_HOST (str): Activity iframe host.
        STRIPE_KEY (str): Stripe publishable key.
        ADYEN_KEY (str): Adyen client key.
        BRAINTREE_KEY (str): Braintree client key.
        PUBLIC_PATH (str): Static asset path prefix.
        SENTRY_RELEASE (str): Sentry release name.
    """

    __slots__ = ()

    BUILD_NUMBER = "BUILD_NUMBER"
    VERSION_HASH = "VERSION_HASH"
    BUILT_AT = "BUILT_AT"
    RELEASE_CHANNEL = "RELEASE_CHANNEL"
    API_VERSION = "API_VERSION"
    GATEWAY_ENDPOINT = "GATEWAY_ENDPOINT"
    API_ENDPOINT = "API_ENDPOINT"
    REMOTE_AUTH_ENDPOINT = "REMOTE_AUTH_ENDPOINT"
    CDN_HOST = "CDN_HOST"
    MEDIA_PROXY_ENDPOINT = "MEDIA_PROXY_ENDPOINT"
    IMAGE_PROXY_ENDPOINTS = "IMAGE_PROXY_ENDPOINTS"
    RTC_LATENCY_ENDPOINT = "RTC_LATENCY_ENDPOINT"
    NETWORKING_ENDPOINT = "NETWORKING_ENDPOINT"
    INVITE_HOST = "INVITE_HOST"
    GIFT_CODE_HOST = "GIFT_CODE_HOST"
    GUILD_TEMPLATE_HOST = "GUILD_TEMPLATE_HOST"
    ACTIVITY_APPLICATION_HOST = "ACTIVITY_APPLICATION_HOST"
    STRIPE_KEY = "STRIPE_KEY"
    ADYEN_KEY = "ADYEN_KEY"
    BRAINTREE_KEY = "BRAINTREE_KEY"
    PUBLIC_PATH = "PUBLIC_PATH"
    SENTRY_RELEASE = "SENTRY_RELEASE"


@unique
class EnvMarker(StrEnum):
    """
    Text that introduces a ``GLOBAL_ENV`` object in the app page.

    Attributes:
        WINDOW (str): ``window.GLOBAL_ENV`` assignment.
        BARE (str): ``GLOBAL_ENV`` mention without the window prefix.
    """

    __slots__ = ()

    WINDOW = "window.GLOBAL_ENV"
    BARE = "GLOBAL_ENV"


@unique
class ScriptKind(StrEnum):
    """
    App script prefixes fetched before the rest of the page.

    Declaration order is fetch order. Earlier members are downloaded first.

    Attributes:
        FAST_CONNECT (str): Identify payload chunk.
        WEB (str): Main web entry chunk.
        SENTRY (str): Sentry loader chunk.
    """

    __slots__ = ()

    FAST_CONNECT = "fast-connect."
    WEB = "web."
    SENTRY = "sentry."

    def rank(self) -> int:
        """
        Return this script's fetch order.

        Returns:
            int: Zero-based rank. Lower values are fetched first.
        """
        return _SCRIPT_RANKS[self]


_SCRIPT_RANKS: dict[ScriptKind, int] = {kind: index for index, kind in enumerate(ScriptKind)}


@unique
class ResponseHeader(StrEnum):
    """
    Response header names read from the app page.

    Attributes:
        BUILD_ID (str): Build hash header.
        LAST_MODIFIED (str): Page modification time.
    """

    __slots__ = ()

    BUILD_ID = "x-build-id"
    LAST_MODIFIED = "last-modified"


@unique
class DataFile(StrEnum):
    """
    JSON files written under the data directory.

    Attributes:
        LATEST (str): Current snapshot of every channel.
        HISTORY (str): Rows appended when identity or capabilities change.
    """

    __slots__ = ()

    LATEST = "latest.json"
    HISTORY = "history.json"


@unique
class ExitCode(IntEnum):
    """
    Process status codes returned by the command line.

    Attributes:
        SUCCESS (int): The run finished.
        FAILURE (int): Configuration, fetch, or scrape failed.
    """

    __slots__ = ()

    SUCCESS = 0
    FAILURE = 1


@unique
class TruthyText(StrEnum):
    """
    Text accepted as true in config and environment variables.

    Attributes:
        ONE (str): Digit one.
        TRUE (str): Word true.
        YES (str): Word yes.
        ON (str): Word on.
    """

    __slots__ = ()

    ONE = "1"
    TRUE = "true"
    YES = "yes"
    ON = "on"


@unique
class FalsyText(StrEnum):
    """
    Text accepted as false in config and environment variables.

    Attributes:
        ZERO (str): Digit zero.
        FALSE (str): Word false.
        NO (str): Word no.
        OFF (str): Word off.
    """

    __slots__ = ()

    ZERO = "0"
    FALSE = "false"
    NO = "no"
    OFF = "off"


@unique
class ClearedText(StrEnum):
    """
    Text that clears an optional string setting.

    Attributes:
        ZERO (str): Digit zero.
        FALSE (str): Word false.
        NONE (str): Word none.
        OFF (str): Word off.
    """

    __slots__ = ()

    ZERO = "0"
    FALSE = "false"
    NONE = "none"
    OFF = "off"
