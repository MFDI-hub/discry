"""Settings from config.toml, environment variables, then CLI flags."""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field, fields, replace
from datetime import datetime, timedelta, timezone, tzinfo as dt_tzinfo
from pathlib import Path
from typing import Any, Final, get_args
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from .enums import (
    AssetExtension,
    ClearedText,
    EnvMarker,
    FalsyText,
    ReleaseChannel,
    ScriptKind,
    TruthyText,
)
from .models import ClientSurface

DEFAULT_CONFIG_PATH: Final = Path("config.toml")
DEFAULT_LATEST_URL: Final = (
    "https://raw.githubusercontent.com/MFDI-hub/discry/main/data/latest.json"
)
DEFAULT_CHANNELS: Final[tuple[str, ...]] = (
    ReleaseChannel.STABLE,
    ReleaseChannel.PTB,
    ReleaseChannel.CANARY,
)
DEFAULT_DOMAINS: Final[dict[str, str]] = {
    ReleaseChannel.STABLE: "discord.com",
    ReleaseChannel.PTB: "ptb.discord.com",
    ReleaseChannel.CANARY: "canary.discord.com",
}
DEFAULT_LATEST_FIELDS: Final[tuple[str, ...]] = tuple(
    item.name for item in fields(ClientSurface) if item.name != "channel"
)
DEFAULT_HISTORY_FIELDS: Final[tuple[str, ...]] = (
    "channel",
    "build_number",
    "version_hash",
    "build_id",
    "capabilities",
    "capability_values",
    "client_build_number",
    "release_channel",
    "built_at",
    "first_seen",
)
DEFAULT_HISTORY_KEY_FIELDS: Final[tuple[str, ...]] = (
    "channel",
    "build_number",
    "version_hash",
    "capabilities",
)
# Stay under GitHub's 100 MB file limit. The open log rolls to a timestamped
# file before a write would reach this size.
DEFAULT_HISTORY_ROTATE_BYTES: Final = 95_000_000
DEFAULT_SCRIPT_PRIORITY: Final[tuple[str, ...]] = tuple(member.value for member in ScriptKind)
DEFAULT_ASSET_EXTENSIONS: Final[tuple[str, ...]] = tuple(member.value for member in AssetExtension)
DEFAULT_ENV_MARKERS: Final[tuple[str, ...]] = tuple(member.value for member in EnvMarker)
DEFAULT_LOG_FORMAT: Final = "%(levelname)s %(name)s: %(message)s"
OUTPUT_FORMATS: Final[frozenset[str]] = frozenset({"json", "md", "csv", "toml", "yaml"})
_FORMAT_ALIASES: Final[dict[str, str]] = {"markdown": "md", "yml": "yaml"}
_TRUTHY: Final[frozenset[str]] = frozenset(member.value for member in TruthyText)
_FALSY: Final[frozenset[str]] = frozenset(member.value for member in FalsyText)
_CLEARED: Final[frozenset[str]] = frozenset(member.value for member in ClearedText)
_SURFACE_FIELDS: Final[frozenset[str]] = frozenset(item.name for item in fields(ClientSurface))
_HISTORY_FIELDS: Final[frozenset[str]] = _SURFACE_FIELDS | {"first_seen"}
_OFFSET = re.compile(r"([+-])(\d{2}):?(\d{2})\Z")
_ENV_ALIAS: Final[dict[str, str]] = {"download_concurrency": "SCRAPER_CONCURRENCY"}
_FIELD_KIND: Final[dict[str, str]] = {}


def _impersonation_names() -> frozenset[str]:
    """
    Return browser profiles known to the installed curl_cffi.

    Returns:
        frozenset[str]: Profile names, or an empty set when curl_cffi cannot
        report them.
    """
    try:
        from curl_cffi.requests import BrowserTypeLiteral
    except Exception:
        return frozenset()
    names = {str(name) for name in get_args(BrowserTypeLiteral) if isinstance(name, str)}
    return frozenset(names)


@dataclass(frozen=True, slots=True)
class Settings:
    """
    Runtime settings for one scrape or snapshot fetch.

    Defaults match the values the scraper used before these fields existed.
    CLI flags win over environment variables, which win over the TOML file.

    Attributes:
        impersonate (str): curl_cffi browser profile.
        proxy (str | None): Proxy URL used for HTTP and HTTPS when the split
            proxies are unset.
        timeout (float): Read timeout in seconds.
        verify (bool): Verify TLS certificates when true.
        channels (tuple[str, ...]): Channels to scrape, in order.
        data_dir (str): Directory for output files.
        max_files (int): Maximum JS files inspected per channel.
        download_concurrency (int): Parallel download limit inside one channel.
        asset_base_url (str | None): Base URL for asset files. None uses the
            channel host.
        headers (dict[str, str]): Extra request headers.
        domains (dict[str, str]): Channel name to hostname.
        output_formats (tuple[str, ...]): Writers for the history log.
            ``json``, ``md``, ``csv``, ``toml``, and ``yaml``.
        latest_formats (tuple[str, ...]): Writers for the snapshot. Empty uses
            ``output_formats``.
        json_indent (int): JSON indent. ``0`` writes compact JSON.
        json_sort_keys (bool): Sort JSON keys when true.
        json_trailing_newline (bool): End JSON files with a newline when true.
        latest_filename (str): File stem for the snapshot.
        history_filename (str): File stem for the history log.
        latest_dir (str | None): Snapshot directory. None uses ``data_dir``.
        history_dir (str | None): History directory. None uses ``data_dir``.
        history_rotate_bytes (int): Close the open history file when a write
            would reach this size. The closed file is renamed with the UTC
            time of the change, and later rows continue in a new file.
        save_client (bool): Save the app page and its scripts under
            ``data/client`` when true.
        client_dir (str | None): Directory for that copy. None uses
            ``data_dir / client``.
        write_output (bool): Write files after a scrape when true.
        write_on_fetch (bool): Write files after ``--from-repo`` when true.
        latest_fields (tuple[str, ...]): Surface fields stored in the snapshot.
        history_fields (tuple[str, ...]): Fields stored on a history row.
        history_key_fields (tuple[str, ...]): Fields that decide whether a
            history row is new. An empty ``version_hash`` falls back to
            ``build_id``.
        drop_nulls (bool): Omit fields whose value is None when true.
        timezone (str): ``UTC``, ``local``, ``+HH:MM``, or an IANA name.
        timestamp_format (str): ``iso`` or a :meth:`datetime.datetime.strftime`
            pattern.
        timestamp_microseconds (bool): Keep microseconds when true.
        scraped_at (str | None): Clock override. None means the current time.
        scraped_at_format (str): Format for ``scraped_at``. Empty uses
            ``timestamp_format``.
        updated_at_format (str): Format for ``updated_at``. Empty uses
            ``timestamp_format``.
        first_seen_format (str): Format for ``first_seen``. Empty uses
            ``timestamp_format``.
        url_scheme (str): ``https`` or ``http``.
        app_path (str): Path fetched on each channel host.
        asset_prefix (str): Asset path prefix searched in the page.
        http_proxy (str | None): HTTP proxy. None uses ``proxy``.
        https_proxy (str | None): HTTPS proxy. None uses ``proxy``.
        no_proxy (str | None): Comma-separated hosts that skip the proxy.
        retries (int): Extra attempts after the first request.
        retry_backoff (float): Seconds times the attempt number between retries.
        max_redirects (int): Redirect limit. ``-1`` means no limit.
        cookies (dict[str, str]): Cookies sent on each request.
        http2 (bool | None): Force HTTP/2 or HTTP/1.1. None leaves the library
            default.
        connect_timeout (float | None): Connect timeout. None uses ``timeout``
            for the whole request.
        curl_options (dict[str, Any]): Extra curl_cffi arguments.
        channel_concurrency (int): Channels fetched at the same time.
        continue_on_error (bool): Return the channels that succeeded when true.
        script_priority (tuple[str, ...]): Script name prefixes fetched first.
        script_extensions (tuple[str, ...]): Script extensions downloaded.
        identity_fields (tuple[str, ...]): Fields that make a scrape successful.
        identity_match (str): ``any`` or ``all`` for ``identity_fields``.
        skip_script_fields (tuple[str, ...]): Fields that must all be set,
            together with the identity fields, before script downloads start.
        rest_script_fields (tuple[str, ...]): When any of these is missing, the
            non-priority scripts are downloaded too.
        stop_fields (tuple[str, ...]): Fields that must all be set before
            downloads stop.
        stop_early_fields (tuple[str, ...]): Extra fields that let downloads
            stop before the priority scripts are finished.
        max_env_chars (int): Maximum ``GLOBAL_ENV`` object size.
        hash_min_length (int): Shortest accepted build hash.
        hash_max_length (int): Longest accepted build hash.
        asset_hash_min_length (int): Shortest accepted asset hash.
        asset_hash_max_length (int): Longest accepted asset hash.
        capability_literal_min_digits (int): Shortest ``capabilities:`` number.
        capability_literal_max_digits (int): Longest ``capabilities:`` number.
        capability_ternary_min_digits (int): Shortest ternary capability number.
        capability_ternary_max_digits (int): Longest ternary capability number.
        build_number_min_digits (int): Shortest accepted build number.
        release_channel_separator (str): Cut the release channel at this text.
            Empty keeps the whole value.
        release_channel_case (str): ``lower``, ``upper``, or ``preserve``.
        empty_values (tuple[str, ...]): Strings treated as a missing value.
        env_markers (tuple[str, ...]): Text that introduces ``GLOBAL_ENV``.
        build_id_header (str): Response header that carries the build id.
        last_modified_header (str): Response header that carries the page time.
        asset_extensions (tuple[str, ...]): Content-hashed extensions to keep.
        latest_url (str): Snapshot URL used by ``--from-repo``.
        from_repo (bool): Read ``latest_url`` instead of scraping when true.
        log_level (str): ``DEBUG``, ``INFO``, ``WARNING``, ``ERROR``, or
            ``CRITICAL``.
        log_format (str): :mod:`logging` format string.
        log_file (str | None): Log file. None logs to stderr.
        domains_replace (bool): Replace the built-in domains when true.
            Otherwise a domains table is merged on top of them.
    """

    impersonate: str = "chrome"
    proxy: str | None = None
    timeout: float = 30
    verify: bool = True
    channels: tuple[str, ...] = DEFAULT_CHANNELS
    data_dir: str = "data"
    max_files: int = 40
    download_concurrency: int = 8
    asset_base_url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    domains: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_DOMAINS))
    output_formats: tuple[str, ...] = ("json",)
    latest_formats: tuple[str, ...] = ()
    json_indent: int = 2
    json_sort_keys: bool = False
    json_trailing_newline: bool = True
    latest_filename: str = "latest"
    history_filename: str = "history"
    latest_dir: str | None = None
    history_dir: str | None = None
    history_rotate_bytes: int = DEFAULT_HISTORY_ROTATE_BYTES
    save_client: bool = True
    client_dir: str | None = None
    write_output: bool = True
    write_on_fetch: bool = False
    latest_fields: tuple[str, ...] = DEFAULT_LATEST_FIELDS
    history_fields: tuple[str, ...] = DEFAULT_HISTORY_FIELDS
    history_key_fields: tuple[str, ...] = DEFAULT_HISTORY_KEY_FIELDS
    drop_nulls: bool = False
    timezone: str = "UTC"
    timestamp_format: str = "iso"
    timestamp_microseconds: bool = True
    scraped_at: str | None = None
    scraped_at_format: str = ""
    updated_at_format: str = ""
    first_seen_format: str = ""
    url_scheme: str = "https"
    app_path: str = "/app"
    asset_prefix: str = "/assets/"
    http_proxy: str | None = None
    https_proxy: str | None = None
    no_proxy: str | None = None
    retries: int = 0
    retry_backoff: float = 0
    max_redirects: int = 30
    cookies: dict[str, str] = field(default_factory=dict)
    http2: bool | None = None
    connect_timeout: float | None = None
    curl_options: dict[str, Any] = field(default_factory=dict)
    channel_concurrency: int = 1
    continue_on_error: bool = False
    script_priority: tuple[str, ...] = DEFAULT_SCRIPT_PRIORITY
    script_extensions: tuple[str, ...] = ("js",)
    identity_fields: tuple[str, ...] = ("build_number", "version_hash", "build_id")
    identity_match: str = "any"
    skip_script_fields: tuple[str, ...] = ("capabilities", "client_build_number")
    rest_script_fields: tuple[str, ...] = ("capabilities", "build_number")
    stop_fields: tuple[str, ...] = ("build_number", "capabilities")
    stop_early_fields: tuple[str, ...] = ("client_build_number",)
    max_env_chars: int = 200_000
    hash_min_length: int = 7
    hash_max_length: int = 64
    asset_hash_min_length: int = 8
    asset_hash_max_length: int = 40
    capability_literal_min_digits: int = 3
    capability_literal_max_digits: int = 10
    capability_ternary_min_digits: int = 4
    capability_ternary_max_digits: int = 10
    build_number_min_digits: int = 4
    release_channel_separator: str = "-"
    release_channel_case: str = "lower"
    empty_values: tuple[str, ...] = ("", "undefined", "null", "none")
    env_markers: tuple[str, ...] = DEFAULT_ENV_MARKERS
    build_id_header: str = "x-build-id"
    last_modified_header: str = "last-modified"
    asset_extensions: tuple[str, ...] = DEFAULT_ASSET_EXTENSIONS
    latest_url: str = DEFAULT_LATEST_URL
    from_repo: bool = False
    log_level: str = "INFO"
    log_format: str = DEFAULT_LOG_FORMAT
    log_file: str | None = None
    domains_replace: bool = False

    def validate(self) -> Settings:
        """
        Check limits, names, formats, and channel domains.

        Returns:
            Settings: This object when every check passes.

        Raises:
            ValueError: A setting is empty, out of range, or inconsistent.
        """
        self._validate_http()
        self._validate_output()
        self._validate_fields()
        self._validate_patterns()
        resolve_timezone(self.timezone)
        if self.scraped_at:
            parse_timestamp(self.scraped_at, self)
        for name in (
            "timestamp_format",
            "scraped_at_format",
            "updated_at_format",
            "first_seen_format",
        ):
            fmt = str(getattr(self, name))
            if fmt and fmt != "iso":
                datetime.now(timezone.utc).strftime(fmt)
        return self

    def _validate_http(self) -> None:
        """
        Check the HTTP settings.

        Raises:
            ValueError: A timeout, proxy profile, or URL piece is invalid.
        """
        known = _impersonation_names()
        if known and self.impersonate not in known:
            allowed = ", ".join(sorted(known))
            raise ValueError(f"Unknown impersonate {self.impersonate!r}. Allowed: {allowed}")
        if not self.impersonate.strip():
            raise ValueError("impersonate must not be empty")
        if self.timeout <= 0:
            raise ValueError("timeout must be greater than 0")
        if self.connect_timeout is not None and self.connect_timeout <= 0:
            raise ValueError("connect_timeout must be greater than 0")
        if self.retries < 0:
            raise ValueError("retries must be at least 0")
        if self.retry_backoff < 0:
            raise ValueError("retry_backoff must be at least 0")
        if self.max_redirects < -1:
            raise ValueError("max_redirects must be at least -1")
        if self.url_scheme not in {"http", "https"}:
            raise ValueError("url_scheme must be http or https")
        if not self.latest_url.strip():
            raise ValueError("latest_url must not be empty")
        level = self.log_level.upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ValueError(f"Unknown log_level {self.log_level!r}")

    def _validate_output(self) -> None:
        """
        Check writers, file names, and the channel list.

        Raises:
            ValueError: A format, name, or channel setting is invalid.
        """
        if self.json_indent < 0:
            raise ValueError("json_indent must be at least 0")
        if not self.output_formats:
            raise ValueError("output_formats must not be empty")
        unknown_formats = [item for item in self.output_formats if item not in OUTPUT_FORMATS]
        if unknown_formats:
            raise ValueError(f"Unknown output format(s): {', '.join(unknown_formats)}")
        unknown_latest = [item for item in self.latest_formats if item not in OUTPUT_FORMATS]
        if unknown_latest:
            raise ValueError(f"Unknown latest format(s): {', '.join(unknown_latest)}")
        if not self.latest_filename.strip() or not self.history_filename.strip():
            raise ValueError("latest_filename and history_filename must not be empty")
        if self.history_rotate_bytes < 1:
            raise ValueError("history_rotate_bytes must be at least 1")
        if self.max_files < 1:
            raise ValueError("max_files must be at least 1")
        if self.download_concurrency < 1:
            raise ValueError("download_concurrency must be at least 1")
        if self.channel_concurrency < 1:
            raise ValueError("channel_concurrency must be at least 1")
        if not self.channels:
            raise ValueError("channels must not be empty")
        unknown = [channel for channel in self.channels if channel not in self.domains]
        if unknown:
            raise ValueError(
                f"No domain configured for channel(s): {', '.join(unknown)}. "
                "Add them under [domains] in config.toml."
            )

    def _validate_fields(self) -> None:
        """
        Check field lists and asset extensions.

        Raises:
            ValueError: A field name or extension is unknown.
        """
        if self.identity_match not in {"any", "all"}:
            raise ValueError("identity_match must be any or all")
        self._require_fields("latest_fields", self.latest_fields, _SURFACE_FIELDS)
        self._require_fields("history_fields", self.history_fields, _HISTORY_FIELDS)
        self._require_fields("history_key_fields", self.history_key_fields, _HISTORY_FIELDS)
        for name in (
            "identity_fields",
            "skip_script_fields",
            "rest_script_fields",
            "stop_fields",
            "stop_early_fields",
        ):
            self._require_fields(name, getattr(self, name), _SURFACE_FIELDS)
        known_ext = {member.value for member in AssetExtension}
        unknown_ext = [item for item in self.asset_extensions if item not in known_ext]
        if unknown_ext:
            raise ValueError(f"Unknown asset extension(s): {', '.join(unknown_ext)}")
        if not self.script_extensions:
            raise ValueError("script_extensions must not be empty")

    def _validate_patterns(self) -> None:
        """
        Check parser limits.

        Raises:
            ValueError: A length or case setting is out of range.
        """
        pairs = (
            ("hash_min_length", "hash_max_length"),
            ("asset_hash_min_length", "asset_hash_max_length"),
            ("capability_literal_min_digits", "capability_literal_max_digits"),
            ("capability_ternary_min_digits", "capability_ternary_max_digits"),
        )
        minimums = (
            "max_env_chars",
            "hash_min_length",
            "hash_max_length",
            "asset_hash_min_length",
            "asset_hash_max_length",
            "capability_literal_min_digits",
            "capability_literal_max_digits",
            "capability_ternary_min_digits",
            "capability_ternary_max_digits",
            "build_number_min_digits",
        )
        for name in minimums:
            if int(getattr(self, name)) < 1:
                raise ValueError(f"{name} must be at least 1")
        for low_name, high_name in pairs:
            if int(getattr(self, low_name)) > int(getattr(self, high_name)):
                raise ValueError(f"{low_name} must be less than or equal to {high_name}")
        if self.release_channel_case not in {"lower", "upper", "preserve"}:
            raise ValueError("release_channel_case must be lower, upper, or preserve")

    @staticmethod
    def _require_fields(name: str, selected: tuple[str, ...], allowed: frozenset[str]) -> None:
        """
        Raise when ``selected`` names a field outside ``allowed``.

        Parameters:
            name (str): Setting name, used in the error.
            selected (tuple[str, ...]): Configured field names.
            allowed (frozenset[str]): Field names the setting may use.

        Raises:
            ValueError: ``selected`` contains an unknown name.
        """
        unknown = [item for item in selected if item not in allowed]
        if unknown:
            raise ValueError(f"Unknown {name}: {', '.join(unknown)}")


def _kind(name: str, kind: str) -> None:
    """
    Record how one settings field is parsed.

    Parameters:
        name (str): Settings attribute.
        kind (str): Parser bucket.
    """
    _FIELD_KIND[name] = kind


for _name in (
    "impersonate",
    "data_dir",
    "latest_filename",
    "history_filename",
    "timezone",
    "timestamp_format",
    "scraped_at_format",
    "updated_at_format",
    "first_seen_format",
    "url_scheme",
    "release_channel_separator",
    "release_channel_case",
    "build_id_header",
    "last_modified_header",
    "latest_url",
    "log_level",
    "log_format",
    "identity_match",
):
    _kind(_name, "str")
for _name in (
    "proxy",
    "asset_base_url",
    "latest_dir",
    "history_dir",
    "client_dir",
    "http_proxy",
    "https_proxy",
    "no_proxy",
    "scraped_at",
    "log_file",
):
    _kind(_name, "optstr")
for _name in ("app_path", "asset_prefix"):
    _kind(_name, "path")
for _name in ("timeout", "retry_backoff"):
    _kind(_name, "float")
_kind("connect_timeout", "optfloat")
for _name in (
    "max_files",
    "download_concurrency",
    "json_indent",
    "retries",
    "max_redirects",
    "channel_concurrency",
    "max_env_chars",
    "hash_min_length",
    "hash_max_length",
    "asset_hash_min_length",
    "asset_hash_max_length",
    "capability_literal_min_digits",
    "capability_literal_max_digits",
    "capability_ternary_min_digits",
    "capability_ternary_max_digits",
    "build_number_min_digits",
    "history_rotate_bytes",
):
    _kind(_name, "int")
for _name in (
    "verify",
    "json_sort_keys",
    "json_trailing_newline",
    "write_output",
    "write_on_fetch",
    "save_client",
    "drop_nulls",
    "timestamp_microseconds",
    "continue_on_error",
    "from_repo",
    "domains_replace",
):
    _kind(_name, "bool")
_kind("http2", "optbool")
for _name in (
    "channels",
    "output_formats",
    "latest_formats",
    "latest_fields",
    "history_fields",
    "history_key_fields",
    "script_priority",
    "script_extensions",
    "identity_fields",
    "skip_script_fields",
    "rest_script_fields",
    "stop_fields",
    "stop_early_fields",
    "empty_values",
    "env_markers",
    "asset_extensions",
):
    _kind(_name, "tuple")
for _name in ("headers", "domains", "cookies"):
    _kind(_name, "strmap")
_kind("curl_options", "anymap")

_UNPARSED = {item.name for item in fields(Settings)} - set(_FIELD_KIND)
if _UNPARSED:  # pragma: no cover
    raise RuntimeError(f"Settings fields missing from the config parser: {sorted(_UNPARSED)}")


def resolve_timezone(name: str) -> dt_tzinfo:
    """
    Return the timezone named by a setting.

    Parameters:
        name (str): ``UTC``, ``local``, a numeric offset, or an IANA name.

    Returns:
        datetime.tzinfo: Timezone used for new timestamps.

    Raises:
        ValueError: ``name`` is empty or unknown.
    """
    text = name.strip()
    if text.upper() in {"UTC", "Z", "GMT"}:
        return timezone.utc
    if text.lower() == "local":
        return datetime.now().astimezone().tzinfo or timezone.utc
    match = _OFFSET.fullmatch(text)
    if match:
        sign = 1 if match.group(1) == "+" else -1
        return timezone(
            timedelta(hours=sign * int(match.group(2)), minutes=sign * int(match.group(3)))
        )
    try:
        return ZoneInfo(text)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone {name!r}") from exc


def parse_timestamp(text: str, settings: Settings) -> datetime:
    """
    Parse a configured timestamp.

    Parameters:
        text (str): Timestamp text.
        settings (Settings): Format and timezone.

    Returns:
        datetime.datetime: Aware timestamp.

    Raises:
        ValueError: ``text`` does not match the configured format.
    """
    raw = text.strip()
    if settings.timestamp_format == "iso":
        moment = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    else:
        moment = datetime.strptime(raw, settings.timestamp_format)
    if moment.tzinfo is None:
        return moment.replace(tzinfo=resolve_timezone(settings.timezone))
    return moment


def resolve_moment(settings: Settings, scraped_at: datetime | str | None = None) -> datetime:
    """
    Choose the clock instant for this run.

    Parameters:
        settings (Settings): Active settings.
        scraped_at (datetime | str | None): Explicit instant. A string is
            parsed with ``settings``. None uses ``settings.scraped_at``, then
            the current time.

    Returns:
        datetime.datetime: Aware timestamp.
    """
    if isinstance(scraped_at, datetime):
        return scraped_at
    text = scraped_at if isinstance(scraped_at, str) and scraped_at.strip() else settings.scraped_at
    if text:
        return parse_timestamp(text, settings)
    return datetime.now(resolve_timezone(settings.timezone))


def format_timestamp(moment: datetime, settings: Settings, field_name: str) -> str:
    """
    Format one stored timestamp.

    Parameters:
        moment (datetime): Instant to format.
        settings (Settings): Timezone, microseconds, and format.
        field_name (str): ``scraped_at``, ``updated_at``, or ``first_seen``.
            The matching ``*_format`` field wins when it is set.

    Returns:
        str: Formatted timestamp.
    """
    fmt = str(getattr(settings, f"{field_name}_format") or settings.timestamp_format)
    zone = resolve_timezone(settings.timezone)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    local = moment.astimezone(zone)
    if not settings.timestamp_microseconds:
        local = local.replace(microsecond=0)
    if fmt == "iso":
        return local.isoformat()
    return local.strftime(fmt)


def _none_if_empty(value: Any) -> str | None:
    """
    Return a stripped string, or None when the value clears the setting.

    Parameters:
        value (Any): Raw config or environment value.

    Returns:
        str | None: Stripped text, or None for empty and cleared values.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in _CLEARED:
        return None
    return text


def _as_bool(value: Any) -> bool:
    """
    Parse a boolean from a bool or from accepted text.

    Parameters:
        value (Any): Raw config or environment value.

    Returns:
        bool: Parsed boolean.

    Raises:
        ValueError: ``value`` is not a boolean and not accepted text.
    """
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in _TRUTHY:
        return True
    if text in _FALSY:
        return False
    raise ValueError(f"Invalid boolean value: {value!r}")


def _as_tuple(value: Any, *, keep_empty: bool = False) -> tuple[str, ...]:
    """
    Return a tuple of strings from a list or a comma-separated string.

    Parameters:
        value (Any): Raw sequence or comma-separated text.
        keep_empty (bool): Keep blank items when true.

    Returns:
        tuple[str, ...]: Stripped items.
    """
    parts = value.split(",") if isinstance(value, str) else list(value)
    items = tuple(str(item).strip() for item in parts)
    if keep_empty:
        return items
    return tuple(item for item in items if item)


def _as_map(value: Any) -> Mapping[str, Any]:
    """
    Return a mapping, parsing a JSON object when ``value`` is text.

    Parameters:
        value (Any): Mapping or JSON object text.

    Returns:
        Mapping[str, Any]: Parsed mapping.

    Raises:
        TypeError: ``value`` is not a mapping.
        json.JSONDecodeError: Text is not a JSON object.
    """
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, Mapping):
        raise TypeError("expected a table of keys and values")
    return value


def _normalize(raw: Mapping[str, Any], *, replace_domains: bool = False) -> dict[str, Any]:
    """
    Coerce present keys into ``Settings`` field types.

    Parameters:
        raw (Mapping[str, Any]): Partial settings mapping.
        replace_domains (bool): Replace the built-in domain map when true.

    Returns:
        dict[str, Any]: Keys that were present, with coerced values.

    Raises:
        TypeError: A table field has the wrong shape.
        ValueError: A boolean cannot be parsed.
    """
    out: dict[str, Any] = {}
    replace = replace_domains
    if "domains_replace" in raw:
        replace = _as_bool(raw["domains_replace"])
    for key, value in raw.items():
        kind = _FIELD_KIND[key]
        if kind == "str":
            out[key] = str(value).strip()
        elif kind == "optstr":
            out[key] = _none_if_empty(value)
        elif kind == "path":
            text = str(value).strip() or "/"
            if not text.startswith("/"):
                text = f"/{text}"
            if key == "asset_prefix" and not text.endswith("/"):
                text = f"{text}/"
            out[key] = text
        elif kind == "float":
            out[key] = float(value)
        elif kind == "optfloat":
            out[key] = None if value is None or str(value).strip() == "" else float(value)
        elif kind == "int":
            out[key] = int(value)
        elif kind == "bool":
            out[key] = _as_bool(value)
        elif kind == "optbool":
            out[key] = None if value is None or str(value).strip() == "" else _as_bool(value)
        elif kind == "tuple":
            out[key] = _as_tuple(value, keep_empty=key == "empty_values")
        elif kind == "strmap":
            out[key] = {str(item): str(item_value) for item, item_value in _as_map(value).items()}
        else:
            out[key] = dict(_as_map(value))
    if isinstance(out.get("asset_base_url"), str):
        out["asset_base_url"] = out["asset_base_url"].rstrip("/")
    for key in ("output_formats", "latest_formats"):
        if key in out:
            out[key] = tuple(_FORMAT_ALIASES.get(item.lower(), item.lower()) for item in out[key])
    if "log_level" in out:
        out["log_level"] = str(out["log_level"]).upper()
    if "url_scheme" in out:
        out["url_scheme"] = str(out["url_scheme"]).lower()
    if "identity_match" in out:
        out["identity_match"] = str(out["identity_match"]).lower()
    if "release_channel_case" in out:
        out["release_channel_case"] = str(out["release_channel_case"]).lower()
    for key in ("asset_extensions", "script_extensions", "empty_values"):
        if key in out:
            out[key] = tuple(item.lower() for item in out[key])
    for key in ("build_id_header", "last_modified_header"):
        if key in out:
            out[key] = str(out[key]).lower()
    if "domains" in out and not replace:
        merged = dict(DEFAULT_DOMAINS)
        merged.update(out["domains"])
        out["domains"] = merged
    return out


def _env_overrides() -> dict[str, Any]:
    """
    Read ``SCRAPER_*`` environment variables.

    Returns:
        dict[str, Any]: Raw overrides for variables that are set.
    """
    raw: dict[str, Any] = {}
    for item in fields(Settings):
        name = _ENV_ALIAS.get(item.name, f"SCRAPER_{item.name.upper()}")
        value = os.getenv(name)
        if value is None or not value.strip():
            continue
        raw[item.name] = value.strip()
    return raw


def _known_raw(raw: Mapping[str, Any]) -> dict[str, Any]:
    """
    Return ``raw`` when every key is a ``Settings`` field.

    Parameters:
        raw (Mapping[str, Any]): Candidate settings.

    Returns:
        dict[str, Any]: Copy of ``raw``.

    Raises:
        ValueError: ``raw`` contains an unknown key.
    """
    known = set(_FIELD_KIND)
    unknown = set(raw) - known
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ValueError(f"Unknown config key(s): {names}")
    return dict(raw)


def _apply(settings: Settings, raw: Mapping[str, Any]) -> Settings:
    """
    Replace settings fields present in ``raw``.

    Parameters:
        settings (Settings): Current settings.
        raw (Mapping[str, Any]): Partial overrides.

    Returns:
        Settings: Updated settings. ``settings`` itself when ``raw`` is empty.
    """
    if not raw:
        return settings
    normalized = _normalize(_known_raw(raw), replace_domains=settings.domains_replace)
    if not normalized:
        return settings
    return replace(settings, **normalized)


def resolve_config_path(config_path: str | Path | None = None) -> Path | None:
    """
    Choose the config file path.

    Parameters:
        config_path (str | Path | None): Explicit path. When omitted, the
            ``SCRAPER_CONFIG`` environment variable is used, then
            ``./config.toml`` if that file exists.

    Returns:
        Path | None: Path to load, or None when no config file applies.
    """
    if config_path is not None:
        return Path(config_path)
    env_path = os.getenv("SCRAPER_CONFIG", "").strip()
    if env_path:
        return Path(env_path)
    if DEFAULT_CONFIG_PATH.is_file():
        return DEFAULT_CONFIG_PATH
    return None


def load_toml(path: Path) -> dict[str, Any]:
    """
    Load a TOML file that contains a table.

    Parameters:
        path (Path): Config file.

    Returns:
        dict[str, Any]: Top-level table.

    Raises:
        TypeError: The file's top-level value is not a table.
    """
    with path.open("rb") as handle:
        payload = tomllib.load(handle)
    if not isinstance(payload, dict):
        raise TypeError(f"{path} must contain a TOML table")
    return payload


def load_settings(
    *,
    config_path: str | Path | None = None,
    overrides: Mapping[str, Any] | None = None,
    environ: bool = True,
) -> Settings:
    """
    Load settings from defaults, a TOML file, the environment, then overrides.

    Parameters:
        config_path (str | Path | None): TOML file. See ``resolve_config_path``.
        overrides (Mapping[str, Any] | None): Fields that replace earlier values.
            None values are ignored.
        environ (bool): Read ``SCRAPER_*`` variables when true.

    Returns:
        Settings: Validated settings.

    Raises:
        FileNotFoundError: ``config_path`` names a file that does not exist.
        ValueError: A file, variable, or override fails validation.
        TypeError: A structured field has the wrong shape.
    """
    settings = Settings()
    path = resolve_config_path(config_path)
    if path is not None:
        if not path.is_file():
            raise FileNotFoundError(f"Config file not found: {path}")
        settings = _apply(settings, load_toml(path))
    if environ:
        settings = _apply(settings, _env_overrides())
    if overrides:
        cleaned = {key: value for key, value in overrides.items() if value is not None}
        settings = _apply(settings, cleaned)
    return settings.validate()
