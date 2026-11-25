"""Pull Discord client values out of HTML and JS without assuming one spelling.

Each value is read from the first source that still looks like that value.
A build that renames a field, switches quote style, or moves the number into a
script leaves the rest of the surface intact.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from typing import TYPE_CHECKING

from .enums import (
    AssetExtension,
    EnvKey,
    EnvMarker,
    GatewayCompress,
    GatewayEncoding,
    ResponseHeader,
    ScriptKind,
)
from .models import Asset, ClientSurface

if TYPE_CHECKING:
    from datetime import datetime

    from .config import Settings
    from .enums import StrEnum

_MAX_ENV_CHARS = 200_000
_HEX_HASH_RE = re.compile(r"[a-f0-9]{7,64}\Z", re.IGNORECASE)
_CAPABILITY_LITERAL_RE = re.compile(r"capabilities\s*:\s*(\d{3,10})\b", re.IGNORECASE)
_CAPABILITY_TERNARY_RE = re.compile(r"\?\s*(\d{4,10})\s*:\s*(\d{4,10})")
_BUILD_KEY_RE = re.compile(
    r"""["']?(?:build[_]?number|BUILD_NUMBER)["']?\s*[:=,]\s*["'](\d{4,})["']""",
    re.IGNORECASE,
)
_PARSEINT_RE = re.compile(r"""parseInt\(\s*["'](\d{4,})["']""")
_ENV_VALUE_RE = r"""(?:"((?:\\.|[^"\\])*)"|'((?:\\.|[^'\\])*)'|(-?\d+(?:\.\d+)?))"""
_MISSING_STRINGS = frozenset({"", "undefined", "null", "none"})


def _alternation(enum_type: type[StrEnum]) -> str:
    """
    Return a regex alternation of enum values.

    Parameters:
        enum_type (type[StrEnum]): Enum whose values are the alternatives.

    Returns:
        str: Escaped values joined with ``|``.
    """
    return "|".join(re.escape(member.value) for member in enum_type)


_ENCODING_GROUP = _alternation(GatewayEncoding)
_COMPRESS_GROUP = _alternation(GatewayCompress)
_ASSET_RE = re.compile(
    r"/assets/(?P<name>[A-Za-z0-9][\w.-]{0,120}?)"
    r"\.(?P<hash>[a-f0-9]{8,40})\.(?P<ext>" + _alternation(AssetExtension) + r")(?!\w)",
    re.IGNORECASE,
)
_SCRIPT_RE = re.compile(
    r"""(?:src|href)\s*=\s*["'](?P<url>/assets/[^"']+\.js)["']""",
    re.IGNORECASE,
)
_ENCODING_RE = re.compile(
    rf"""["']({_ENCODING_GROUP})["']|(?:encoding=)({_ENCODING_GROUP})""",
    re.IGNORECASE,
)
_COMPRESS_RE = re.compile(
    rf"""["']({_COMPRESS_GROUP})["']|compress=({_COMPRESS_GROUP})""",
    re.IGNORECASE,
)


def _script_pattern(settings: Settings | None) -> re.Pattern[str]:
    """
    Return the script-tag pattern for ``settings``.

    Parameters:
        settings (Settings | None): Asset prefix and script extensions. None
            uses the built-in pattern.

    Returns:
        re.Pattern[str]: Pattern with a ``url`` group.
    """
    if settings is None or (
        settings.asset_prefix == "/assets/" and settings.script_extensions == ("js",)
    ):
        return _SCRIPT_RE
    prefix = re.escape(settings.asset_prefix)
    extensions = "|".join(re.escape(item.lstrip(".")) for item in settings.script_extensions)
    return re.compile(
        rf"""(?:src|href)\s*=\s*["'](?P<url>{prefix}[^"']+\.(?:{extensions}))["']""",
        re.IGNORECASE,
    )


def script_paths(html: str, settings: Settings | None = None) -> list[str]:
    """
    Return asset script URLs from the app HTML, de-duplicated, in order.

    Parameters:
        html (str): App page HTML.
        settings (Settings | None): Asset prefix and script extensions. None
            searches ``/assets/*.js``.

    Returns:
        list[str]: Script paths, without a query string or fragment.
    """
    seen: set[str] = set()
    paths: list[str] = []
    for match in _script_pattern(settings).finditer(html):
        url = match.group("url").split("?", 1)[0].split("#", 1)[0]
        if url in seen:
            continue
        seen.add(url)
        paths.append(url)
    return paths


def _priority_prefixes(settings: Settings | None) -> tuple[str, ...]:
    """
    Return the script prefixes fetched first.

    Parameters:
        settings (Settings | None): Active settings. None uses ``ScriptKind``.

    Returns:
        tuple[str, ...]: Prefixes in fetch order.
    """
    if settings is None:
        return tuple(member.value for member in ScriptKind)
    return settings.script_priority


def _rank_path(path: str, prefixes: tuple[str, ...] | None = None) -> tuple[int, str]:
    """
    Return the fetch rank and file name for one asset path.

    Parameters:
        path (str): Script URL path.
        prefixes (tuple[str, ...] | None): Prefixes in fetch order. None uses
            ``ScriptKind``.

    Returns:
        tuple[int, str]: Rank, then the file name. Paths outside the prefixes
        use the rank after the last prefix.
    """
    ordered = prefixes if prefixes is not None else tuple(member.value for member in ScriptKind)
    name = path.rsplit("/", 1)[-1].lower()
    if ordered == tuple(member.value for member in ScriptKind):
        for kind in ScriptKind:
            if name.startswith(kind):
                return (kind.rank(), name)
        return (len(ScriptKind), name)
    for index, prefix in enumerate(ordered):
        if name.startswith(prefix):
            return (index, name)
    return (len(ordered), name)


def partition_scripts(
    paths: list[str],
    settings: Settings | None = None,
) -> tuple[list[str], list[str]]:
    """
    Put the entry chunks that carry identify data ahead of the rest.

    Parameters:
        paths (list[str]): Script paths from the app page.
        settings (Settings | None): Priority prefixes. None uses ``ScriptKind``.

    Returns:
        tuple[list[str], list[str]]: Priority scripts in fetch order, then the
        remaining scripts in their original order.
    """
    prefixes = _priority_prefixes(settings)

    def rank(path: str) -> tuple[int, str]:
        return _rank_path(path, prefixes)

    other = len(prefixes)
    priority = [path for path in paths if rank(path)[0] < other]
    priority.sort(key=rank)
    rest = [path for path in paths if rank(path)[0] == other]
    return priority, rest


def _stamp(scraped_at: datetime | None, settings: Settings | None) -> str:
    """
    Return the stored scrape timestamp.

    Parameters:
        scraped_at (datetime | None): Instant to format. None stores an empty
            string.
        settings (Settings | None): Timestamp format. None uses ``isoformat``.

    Returns:
        str: Formatted timestamp, or an empty string.
    """
    if scraped_at is None:
        return ""
    if settings is None:
        return scraped_at.isoformat()
    from .config import format_timestamp

    return format_timestamp(scraped_at, settings, "scraped_at")


def parse_global_env(text: str, settings: Settings | None = None) -> dict[str, object]:
    """
    Return the ``GLOBAL_ENV`` object, or the keys a regex can still see.

    Parameters:
        text (str): HTML or script text.
        settings (Settings | None): Env markers, size cap, and empty values.
            None uses the built-in parser.

    Returns:
        dict[str, object]: Environment keys and values. A regex hit fills a key
        the object parse missed.
    """
    raw = _best_env_object(text, settings)
    parsed: dict[str, object] = {}
    if raw:
        parsed = _loads_env(raw)
    extras = _regex_env(raw or text, settings)
    for key, value in extras.items():
        parsed.setdefault(key, value)
    return parsed


def _asset_pattern(settings: Settings | None) -> re.Pattern[str]:
    """
    Return the content-hashed asset pattern.

    Parameters:
        settings (Settings | None): Prefix, extensions, and hash length. None
            uses the built-in pattern.

    Returns:
        re.Pattern[str]: Pattern with ``name``, ``hash``, and ``ext`` groups.
    """
    if settings is None or (
        settings.asset_prefix == "/assets/"
        and settings.asset_extensions == tuple(member.value for member in AssetExtension)
        and settings.asset_hash_min_length == 8
        and settings.asset_hash_max_length == 40
    ):
        return _ASSET_RE
    prefix = re.escape(settings.asset_prefix)
    extensions = "|".join(re.escape(item) for item in settings.asset_extensions)
    low = settings.asset_hash_min_length
    high = settings.asset_hash_max_length
    return re.compile(
        prefix
        + r"(?P<name>[A-Za-z0-9][\w.-]{0,120}?)"
        + rf"\.(?P<hash>[a-f0-9]{{{low},{high}}})\.(?P<ext>{extensions})(?!\w)",
        re.IGNORECASE,
    )


def extract_assets(text: str, settings: Settings | None = None) -> tuple[Asset, ...]:
    """
    Return content-hashed files linked from ``text``.

    Parameters:
        text (str): HTML or script text.
        settings (Settings | None): Prefix, extensions, and hash length. None
            uses the built-in pattern.

    Returns:
        tuple[Asset, ...]: Unique files in the order they appear.
    """
    seen: set[tuple[str, str, str]] = set()
    assets: list[Asset] = []
    for match in _asset_pattern(settings).finditer(text):
        item = (
            match.group("name"),
            match.group("hash").lower(),
            match.group("ext").lower(),
        )
        if item in seen:
            continue
        seen.add(item)
        assets.append(
            Asset(name=item[0], content_hash=item[1], ext=AssetExtension(item[2])),
        )
    return tuple(assets)


def _capability_patterns(
    settings: Settings | None,
) -> tuple[re.Pattern[str], re.Pattern[str]]:
    """
    Return the capability literal and ternary patterns.

    Parameters:
        settings (Settings | None): Digit lengths. None uses the built-in
            patterns.

    Returns:
        tuple[re.Pattern[str], re.Pattern[str]]: Literal pattern, then ternary
        pattern.
    """
    if settings is None or (
        settings.capability_literal_min_digits == 3
        and settings.capability_literal_max_digits == 10
        and settings.capability_ternary_min_digits == 4
        and settings.capability_ternary_max_digits == 10
    ):
        return _CAPABILITY_LITERAL_RE, _CAPABILITY_TERNARY_RE
    literal = re.compile(
        r"capabilities\s*:\s*(\d{"
        + f"{settings.capability_literal_min_digits},{settings.capability_literal_max_digits}"
        + r"})\b",
        re.IGNORECASE,
    )
    low = settings.capability_ternary_min_digits
    high = settings.capability_ternary_max_digits
    ternary = re.compile(rf"\?\s*(\d{{{low},{high}}})\s*:\s*(\d{{{low},{high}}})")
    return literal, ternary


def extract_capabilities(
    text: str,
    settings: Settings | None = None,
) -> tuple[int | None, tuple[int, ...]]:
    """
    Return the capability mask the client sends, plus every mask found beside that field.

    A literal ``capabilities:1767421`` is that mask. A choice
    (``flag ? 1767421 : 1734653``) uses the first branch, and both numbers are
    kept. Several different literals resolve to the largest mask.

    Parameters:
        text (str): HTML or script text.
        settings (Settings | None): Digit lengths. None uses the built-in
            patterns.

    Returns:
        tuple[int | None, tuple[int, ...]]: Primary mask, then every distinct
        mask in ascending order.
    """
    literal_re, ternary_re = _capability_patterns(settings)
    literals = [int(match.group(1)) for match in literal_re.finditer(text)]
    found: list[int] = list(literals)
    truthy: list[int] = []
    for match in re.finditer(r"capabilities\s*:", text, re.IGNORECASE):
        window = text[match.end() : match.end() + 500]
        for pair in ternary_re.finditer(window):
            truthy.append(int(pair.group(1)))
            found.append(int(pair.group(1)))
            found.append(int(pair.group(2)))
    if literals:
        primary: int | None = max(literals)
    elif truthy:
        primary = truthy[0]
    else:
        primary = None
    return primary, tuple(sorted(set(found)))


def _digits(settings: Settings | None) -> int:
    """
    Return the shortest accepted build number.

    Parameters:
        settings (Settings | None): Active settings. None uses 4 digits.

    Returns:
        int: Minimum digit count.
    """
    if settings is None:
        return 4
    return settings.build_number_min_digits


def extract_client_build_numbers(text: str, settings: Settings | None = None) -> tuple[int, ...]:
    """
    Return numbers assigned to ``client_build_number``, including a nearby ``parseInt``.

    Parameters:
        text (str): HTML or script text.
        settings (Settings | None): Minimum digits. None uses 4.

    Returns:
        tuple[int, ...]: Numbers in first-seen order.
    """
    minimum = _digits(settings)
    parseint = (
        _PARSEINT_RE
        if minimum == 4
        else re.compile(rf"""parseInt\(\s*["'](\d{{{minimum},}})["']""")
    )
    found: list[int] = []
    for match in re.finditer(r"client_build_number", text):
        window = text[max(0, match.start() - 120) : match.end() + 80]
        found.extend(int(number) for number in parseint.findall(window))
        found.extend(
            int(number)
            for number in re.findall(
                rf"""client_build_number["']?\s*[:=]\s*["']?(\d{{{minimum},}})""",
                window,
            )
        )
    return tuple(dict.fromkeys(found))


def extract_build_numbers(text: str, settings: Settings | None = None) -> tuple[int, ...]:
    """
    Return build numbers named as ``build_number``, ``buildNumber``, or ``BUILD_NUMBER``.

    Parameters:
        text (str): HTML or script text.
        settings (Settings | None): Minimum digits. None uses 4.

    Returns:
        tuple[int, ...]: Numbers in first-seen order.
    """
    pattern = _BUILD_KEY_RE
    minimum = _digits(settings)
    if minimum != 4:
        pattern = re.compile(
            rf"""["']?(?:build[_]?number|BUILD_NUMBER)["']?\s*[:=,]\s*["'](\d{{{minimum},}})["']""",
            re.IGNORECASE,
        )
    return tuple(dict.fromkeys(int(number) for number in pattern.findall(text)))


def extract_gateway_encoding(text: str) -> tuple[GatewayEncoding, ...]:
    """
    Return gateway encodings named near an ``encoding`` field.

    Parameters:
        text (str): HTML or script text.

    Returns:
        tuple[GatewayEncoding, ...]: Encodings in first-seen order.
    """
    found: list[GatewayEncoding] = []
    for match in re.finditer(r"encoding", text, re.IGNORECASE):
        window = text[max(0, match.start() - 250) : match.end() + 120]
        for groups in _ENCODING_RE.findall(window):
            value = next((part for part in groups if part), "")
            if value:
                found.append(GatewayEncoding(value.lower()))
    return tuple(dict.fromkeys(found))


def extract_gateway_compress(text: str) -> tuple[GatewayCompress, ...]:
    """
    Return gateway compression modes named in ``text``.

    Parameters:
        text (str): HTML or script text.

    Returns:
        tuple[GatewayCompress, ...]: Modes in first-seen order.
    """
    found: list[GatewayCompress] = []
    for groups in _COMPRESS_RE.findall(text):
        value = next((part for part in groups if part), "")
        if value:
            found.append(GatewayCompress(value.lower()))
    return tuple(dict.fromkeys(found))


def assemble_surface(
    *,
    channel: str,
    html: str,
    scripts: list[str] | tuple[str, ...] = (),
    headers: Mapping[str, str] | None = None,
    scraped_at: datetime | None = None,
    settings: Settings | None = None,
) -> ClientSurface:
    """
    Merge the app HTML, optional script bodies, and response headers.

    Parameters:
        channel (str): Channel that was scraped.
        html (str): App page HTML.
        scripts (list[str] | tuple[str, ...]): Script bodies already downloaded.
        headers (Mapping[str, str] | None): Response headers from the app page.
        scraped_at (datetime | None): Timestamp stored on the surface.
        settings (Settings | None): Parser limits and the timestamp format.
            None keeps the built-in parser and ``isoformat``.

    Returns:
        ClientSurface: Merged values. Missing fields stay ``None`` or empty.
    """
    env = parse_global_env(html, settings)
    header_map = {str(key).lower(): str(value) for key, value in (headers or {}).items() if value}
    script_text = "\n".join(scripts)
    searchable = html if not script_text else f"{html}\n{script_text}"

    env_build = _as_int(_env_get(env, EnvKey.BUILD_NUMBER, settings), settings)
    named_builds = extract_build_numbers(html, settings)
    client_builds = extract_client_build_numbers(searchable, settings)
    if env_build is None and not named_builds and script_text:
        named_builds = extract_build_numbers(script_text, settings)
    build_number = env_build
    if build_number is None and named_builds:
        build_number = named_builds[0]
    if build_number is None and client_builds:
        build_number = client_builds[0]

    version_hash = _hex_hash(
        _as_text(_env_get(env, EnvKey.VERSION_HASH, settings), settings), settings
    )
    if version_hash is None:
        version_hash = _hex_hash(_sentry_build_id(env, settings), settings)
    if version_hash is None:
        version_hash = _hash_in_release(
            _as_text(_env_get(env, EnvKey.SENTRY_RELEASE, settings), settings)
        )
    build_header = ResponseHeader.BUILD_ID if settings is None else settings.build_id_header
    modified_header = (
        ResponseHeader.LAST_MODIFIED if settings is None else settings.last_modified_header
    )
    build_id = _hex_hash(header_map.get(str(build_header).lower()), settings)
    if version_hash is None:
        version_hash = build_id
    if build_id is None:
        build_id = version_hash

    capabilities, capability_values = extract_capabilities(searchable, settings)
    assets = extract_assets(html, settings) or extract_assets(script_text, settings)
    release = _as_text(_env_get(env, EnvKey.RELEASE_CHANNEL, settings), settings)
    separator = "-" if settings is None else settings.release_channel_separator
    case = "lower" if settings is None else settings.release_channel_case
    if release:
        if separator:
            release = release.split(separator, 1)[0]
        release = release.strip()
        if case == "lower":
            release = release.lower()
        elif case == "upper":
            release = release.upper()
        release = release or None
    if not release:
        release = channel

    return ClientSurface(
        channel=channel,
        build_number=build_number,
        version_hash=version_hash,
        build_id=build_id,
        built_at=_as_text(_env_get(env, EnvKey.BUILT_AT, settings), settings),
        last_modified=header_map.get(str(modified_header).lower()),
        release_channel=release,
        api_version=_as_int(_env_get(env, EnvKey.API_VERSION, settings), settings),
        gateway_endpoint=_as_text(_env_get(env, EnvKey.GATEWAY_ENDPOINT, settings), settings),
        api_endpoint=_as_text(_env_get(env, EnvKey.API_ENDPOINT, settings), settings),
        remote_auth_endpoint=_as_text(
            _env_get(env, EnvKey.REMOTE_AUTH_ENDPOINT, settings), settings
        ),
        cdn_host=_as_text(_env_get(env, EnvKey.CDN_HOST, settings), settings),
        media_proxy_endpoint=_as_text(
            _env_get(env, EnvKey.MEDIA_PROXY_ENDPOINT, settings), settings
        ),
        image_proxy_endpoints=_as_text(
            _env_get(env, EnvKey.IMAGE_PROXY_ENDPOINTS, settings), settings
        ),
        rtc_latency_endpoint=_as_text(
            _env_get(env, EnvKey.RTC_LATENCY_ENDPOINT, settings), settings
        ),
        networking_endpoint=_as_text(_env_get(env, EnvKey.NETWORKING_ENDPOINT, settings), settings),
        invite_host=_as_text(_env_get(env, EnvKey.INVITE_HOST, settings), settings),
        gift_code_host=_as_text(_env_get(env, EnvKey.GIFT_CODE_HOST, settings), settings),
        guild_template_host=_as_text(_env_get(env, EnvKey.GUILD_TEMPLATE_HOST, settings), settings),
        activity_application_host=_as_text(
            _env_get(env, EnvKey.ACTIVITY_APPLICATION_HOST, settings), settings
        ),
        assets=assets,
        gateway_encoding=extract_gateway_encoding(searchable),
        gateway_compress=extract_gateway_compress(searchable),
        stripe_key=_as_text(_env_get(env, EnvKey.STRIPE_KEY, settings), settings),
        adyen_key=_as_text(_env_get(env, EnvKey.ADYEN_KEY, settings), settings),
        braintree_key=_as_text(_env_get(env, EnvKey.BRAINTREE_KEY, settings), settings),
        capabilities=capabilities,
        capability_values=capability_values,
        client_build_number=client_builds[0] if client_builds else None,
        scraped_at=_stamp(scraped_at, settings),
    )


def _best_env_object(text: str, settings: Settings | None = None) -> str | None:
    """
    Return the ``GLOBAL_ENV`` object most likely to hold the build number.

    Parameters:
        text (str): HTML or script text.
        settings (Settings | None): Env markers and size cap.

    Returns:
        str | None: Object text, preferring one that names the build number.
        The longest object is used when none of them name it.
    """
    best: str | None = None
    for raw in _iter_env_objects(text, settings):
        if best is None or len(raw) > len(best):
            best = raw
        if "BUILD_NUMBER" in raw.upper() or "buildNumber" in raw:
            return raw
    return best


def _iter_env_objects(text: str, settings: Settings | None = None) -> list[str]:
    """
    Return every brace-balanced object that follows a ``GLOBAL_ENV`` marker.

    Parameters:
        text (str): HTML or script text.
        settings (Settings | None): Markers and the maximum object size.

    Returns:
        list[str]: Object texts, including the surrounding braces.
    """
    markers = tuple(EnvMarker) if settings is None else settings.env_markers
    limit = _MAX_ENV_CHARS if settings is None else settings.max_env_chars
    found: list[str] = []
    for marker in markers:
        start = 0
        while True:
            index = text.find(marker, start)
            if index < 0:
                break
            brace = text.find("{", index, index + 80)
            if brace < 0:
                start = index + len(marker)
                continue
            end = _match_brace(text, brace, brace + limit)
            if end is not None:
                found.append(text[brace:end])
            start = index + len(marker)
    return found


def _match_brace(text: str, open_index: int, limit: int) -> int | None:
    """
    Return the index just past the brace that closes ``text[open_index]``.

    Parameters:
        text (str): Source text.
        open_index (int): Index of the opening ``{``.
        limit (int): Index at which the search stops.

    Returns:
        int | None: Index after the matching ``}``, or None when the object
        is truncated or still open at ``limit``.
    """
    depth = 0
    quote: str | None = None
    index = open_index
    end = min(len(text), limit)
    while index < end:
        char = text[index]
        if quote is not None:
            if char == "\\":
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue
        if char in {'"', "'"}:
            quote = char
            index += 1
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    return None


def _loads_env(raw: str) -> dict[str, object]:
    """
    Parse a ``GLOBAL_ENV`` object after rewriting JavaScript-only tokens.

    Parameters:
        raw (str): Object text, including the surrounding braces.

    Returns:
        dict[str, object]: Parsed keys. Empty when the object is not JSON
        after the rewrite.
    """
    cleaned = re.sub(r":\s*Date\.now\(\)", ": null", raw)
    cleaned = re.sub(r":\s*undefined\b", ": null", cleaned)
    cleaned = re.sub(r":\s*void\s+0\b", ": null", cleaned)
    cleaned = re.sub(r",\s*([}\]])", r"\1", cleaned)
    try:
        loaded = json.loads(cleaned)
    except json.JSONDecodeError:
        return {}
    if isinstance(loaded, dict):
        return {str(key): value for key, value in loaded.items()}
    return {}


def _key_variants(key: str) -> tuple[str, ...]:
    """
    Return the canonical, lower, and camelCase spellings of one env key.

    Parameters:
        key (str): Canonical ``GLOBAL_ENV`` name.

    Returns:
        tuple[str, ...]: Spellings, with duplicates removed.
    """
    parts = key.lower().split("_")
    camel = parts[0] + "".join(part.title() for part in parts[1:])
    return tuple(dict.fromkeys((key, key.lower(), camel)))


def _missing_strings(settings: Settings | None) -> frozenset[str]:
    """
    Return the strings treated as a missing value.

    Parameters:
        settings (Settings | None): Active settings. None uses the built-in set.

    Returns:
        frozenset[str]: Lowercase placeholders, including an empty string when
        that is configured.
    """
    if settings is None:
        return _MISSING_STRINGS
    return frozenset(item.lower() for item in settings.empty_values)


def _regex_env(text: str, settings: Settings | None = None) -> dict[str, object]:
    """
    Return ``GLOBAL_ENV`` keys a regex can still see when JSON parsing fails.

    Parameters:
        text (str): Object text or the wider page.
        settings (Settings | None): Strings treated as missing.

    Returns:
        dict[str, object]: Keys from ``EnvKey`` and the first value found for
        each one.
    """
    missing = _missing_strings(settings)
    found: dict[str, object] = {}
    for key in EnvKey:
        for variant in _key_variants(key):
            match = re.search(
                rf"""["']?{re.escape(variant)}["']?\s*:\s*{_ENV_VALUE_RE}""",
                text,
                re.IGNORECASE,
            )
            if not match:
                continue
            value: object = next(group for group in match.groups() if group is not None)
            if isinstance(value, str) and value.lower() in missing:
                break
            found[key] = value
            break
    return found


def _folded_env(env: Mapping[str, object]) -> dict[str, object]:
    """
    Return ``env`` keyed by letters and digits only.

    Parameters:
        env (Mapping[str, object]): Parsed environment.

    Returns:
        dict[str, object]: Folded keys. A later key overwrites an earlier one
        that folds to the same text.
    """
    folded: dict[str, object] = {}
    for key, value in env.items():
        folded[re.sub(r"[^a-z0-9]", "", str(key).lower())] = value
    return folded


def _env_get(
    env: Mapping[str, object], key: str, settings: Settings | None = None
) -> object | None:
    """
    Return one environment value, accepting camelCase and lower_snake keys.

    Parameters:
        env (Mapping[str, object]): Parsed environment.
        key (str): Canonical key.
        settings (Settings | None): Strings treated as missing.

    Returns:
        object | None: The value, or None when it is missing or a placeholder.
    """
    folded = _folded_env(env)
    for variant in _key_variants(key):
        value = folded.get(re.sub(r"[^a-z0-9]", "", variant.lower()))
        if _present(value, settings):
            return value
    return None


def _sentry_build_id(env: Mapping[str, object], settings: Settings | None = None) -> str | None:
    """
    Return the Sentry ``buildId`` tag when the environment carries one.

    Parameters:
        env (Mapping[str, object]): Parsed environment.
        settings (Settings | None): Strings treated as missing.

    Returns:
        str | None: Build id, or None when the tag is absent.
    """
    folded = _folded_env(env)
    tags = folded.get("sentrytags")
    if not isinstance(tags, Mapping):
        return None
    for key, value in tags.items():
        if re.sub(r"[^a-z0-9]", "", str(key).lower()) == "buildid" and _present(value, settings):
            return str(value)
    return None


def _hash_in_release(value: str | None) -> str | None:
    """
    Return a 40-character hex hash embedded in a Sentry release name.

    Parameters:
        value (str | None): Release name.

    Returns:
        str | None: Lowercase hash, or None when ``value`` has none.
    """
    if not value:
        return None
    match = re.search(r"[a-f0-9]{40}", value, re.IGNORECASE)
    if match is None:
        return None
    return match.group(0).lower()


def _present(value: object, settings: Settings | None = None) -> bool:
    """
    Return whether ``value`` is a usable environment value.

    Parameters:
        value (object): Candidate value.
        settings (Settings | None): Strings treated as missing.

    Returns:
        bool: False for None and for blank or placeholder strings.
    """
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() not in _missing_strings(settings)
    return True


def _as_text(value: object, settings: Settings | None = None) -> str | None:
    """
    Return ``value`` as stripped text.

    Parameters:
        value (object): Candidate value.
        settings (Settings | None): Strings treated as missing.

    Returns:
        str | None: Text, or None for placeholders, booleans, and other types.
        Whole-number floats are rendered as integers.
    """
    if not _present(value, settings):
        return None
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not value.is_integer():
            return str(value)
        return str(int(value))
    return None


def _as_int(value: object, settings: Settings | None = None) -> int | None:
    """
    Return ``value`` as an integer.

    Parameters:
        value (object): Candidate value.
        settings (Settings | None): Strings treated as missing.

    Returns:
        int | None: Integer, or None when ``value`` is a boolean, a placeholder,
        or not a whole number.
    """
    if isinstance(value, bool) or not _present(value, settings):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if re.fullmatch(r"-?\d+", text):
            return int(text)
    return None


def _hex_hash(value: str | None, settings: Settings | None = None) -> str | None:
    """
    Return ``value`` when it is a hex build hash.

    Parameters:
        value (str | None): Candidate hash.
        settings (Settings | None): Accepted hash length. None accepts 7 to 64
            hex digits.

    Returns:
        str | None: Lowercase hash, or None.
    """
    if value is None:
        return None
    text = value.strip()
    pattern = _HEX_HASH_RE
    if settings is not None and (settings.hash_min_length != 7 or settings.hash_max_length != 64):
        pattern = re.compile(
            rf"[a-f0-9]{{{settings.hash_min_length},{settings.hash_max_length}}}\Z",
            re.IGNORECASE,
        )
    if pattern.fullmatch(text):
        return text.lower()
    return None
