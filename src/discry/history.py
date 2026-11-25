"""Write the snapshot and append new rows to the history log."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

import orjson

from .config import (
    DEFAULT_HISTORY_KEY_FIELDS,
    Settings,
    format_timestamp,
    resolve_moment,
)

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime

    from .models import ClientSurface

_EXTENSIONS = {"json": "json", "md": "md", "csv": "csv", "toml": "toml", "yaml": "yaml"}
_INT_KEY_FIELDS = {"build_number", "capabilities", "client_build_number", "api_version"}


def load_json(path: Path, default: Any) -> Any:
    """
    Read a JSON file, or return ``default`` when it is missing or empty.

    Parameters:
        path (Path): File to read.
        default (Any): Value used when the file is absent or blank.

    Returns:
        Any: Parsed JSON, or ``default``.
    """
    if not path.exists():
        return default
    payload = path.read_bytes().strip()
    if not payload:
        return default
    return orjson.loads(payload)


def dump_json(path: Path, payload: Any, settings: Settings | None = None) -> None:
    """
    Write JSON, creating parent directories.

    Parameters:
        path (Path): Destination file.
        payload (Any): Value the JSON writer can encode.
        settings (Settings | None): Indent, key order, and trailing newline.
            Defaults to ``Settings()``.
    """
    settings = settings or Settings()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(payload, settings))


def _json_bytes(payload: Any, settings: Settings) -> bytes:
    """
    Encode ``payload`` as JSON bytes.

    Parameters:
        payload (Any): Value to encode.
        settings (Settings): Indent, key order, and trailing newline.

    Returns:
        bytes: Encoded JSON.
    """
    if settings.json_indent == 2 and not settings.json_sort_keys:
        encoded = orjson.dumps(payload, option=orjson.OPT_INDENT_2)
    else:
        indent = None if settings.json_indent <= 0 else settings.json_indent
        encoded = json.dumps(
            payload,
            indent=indent,
            sort_keys=settings.json_sort_keys,
        ).encode()
    if settings.json_trailing_newline:
        return encoded + b"\n"
    return encoded


def history_key(
    row: Mapping[str, Any],
    key_fields: tuple[str, ...] | None = None,
) -> tuple[Any, ...]:
    """
    Return the identity used to decide whether a history row is new.

    Parameters:
        row (Mapping[str, Any]): History row or an equivalent mapping.
        key_fields (tuple[str, ...] | None): Fields that form the key. None
            uses the default channel, build number, version hash, and
            capabilities. An empty version hash falls back to the build id.

    Returns:
        tuple[Any, ...]: One entry per key field.
    """
    selected = key_fields or DEFAULT_HISTORY_KEY_FIELDS
    parts: list[Any] = []
    for name in selected:
        value = row.get(name)
        if name == "version_hash" and not value:
            value = row.get("build_id")
        if name in _INT_KEY_FIELDS:
            parts.append(None if value is None or value == "" else int(value))
        else:
            parts.append("" if value is None else str(value))
    return tuple(parts)


def _project_surface(
    surface: ClientSurface,
    selected: tuple[str, ...],
    *,
    drop_nulls: bool,
    first_seen: str | None = None,
) -> dict[str, Any]:
    """
    Return the configured fields for one surface.

    Parameters:
        surface (ClientSurface): Surface to project.
        selected (tuple[str, ...]): Field names to keep, in order.
        drop_nulls (bool): Omit fields whose value is None when true.
        first_seen (str | None): History timestamp. Included when that field
            is selected.

    Returns:
        dict[str, Any]: Selected fields.
    """
    payload: dict[str, Any] = dict(surface.to_dict())
    payload["channel"] = surface.channel
    if first_seen is not None:
        payload["first_seen"] = first_seen
    chosen: dict[str, Any] = {}
    for name in selected:
        if name not in payload:
            continue
        value = payload[name]
        if drop_nulls and value is None:
            continue
        chosen[name] = value
    return chosen


def merge_history(
    history: list[Mapping[str, Any]],
    surfaces: list[ClientSurface],
    scraped_at: datetime | None = None,
    settings: Settings | None = None,
) -> tuple[dict[str, Any], list[Mapping[str, Any]]]:
    """
    Build the latest snapshot and append unseen surfaces to history.

    Parameters:
        history (list[Mapping[str, Any]]): Rows already stored.
        surfaces (list[ClientSurface]): Surfaces from this run.
        scraped_at (datetime | None): Timestamp stored on new rows. None uses
            the settings clock.
        settings (Settings | None): Field lists, formats, and the clock.
            Defaults to ``Settings()``.

    Returns:
        tuple[dict[str, Any], list[Mapping[str, Any]]]: Latest document, then the
        combined history.
    """
    settings = settings or Settings()
    moment = resolve_moment(settings, scraped_at)
    updated_at = format_timestamp(moment, settings, "updated_at")
    first_seen = format_timestamp(moment, settings, "first_seen")
    latest: dict[str, Any] = {
        "updated_at": updated_at,
        "channels": {
            surface.channel: _project_surface(
                surface,
                settings.latest_fields,
                drop_nulls=settings.drop_nulls,
            )
            for surface in surfaces
        },
    }
    existing = {history_key(row, settings.history_key_fields) for row in history}
    merged: list[Mapping[str, Any]] = list(history)
    for surface in surfaces:
        row = _project_surface(
            surface,
            settings.history_fields,
            drop_nulls=settings.drop_nulls,
            first_seen=first_seen,
        )
        key = history_key(row, settings.history_key_fields)
        if key not in existing:
            merged.append(row)
            existing.add(key)
    return latest, merged


def _markdown(payload: Any, title: str) -> str:
    """
    Return a Markdown document for a snapshot or a history list.

    Parameters:
        payload (Any): Latest document or history rows.
        title (str): Document heading.

    Returns:
        str: Markdown text ending in a newline.
    """
    lines = [f"# {title}", ""]
    if isinstance(payload, dict) and isinstance(payload.get("channels"), dict):
        lines.append(f"- updated_at: {payload.get('updated_at', '')}")
        lines.append("")
        for name, body in payload["channels"].items():
            lines.append(f"## {name}")
            lines.append("")
            lines.append(_markdown_table(body if isinstance(body, dict) else {"value": body}))
            lines.append("")
    elif isinstance(payload, list):
        for index, row in enumerate(payload, start=1):
            lines.append(f"## {index}")
            lines.append("")
            lines.append(_markdown_table(row if isinstance(row, dict) else {"value": row}))
            lines.append("")
    else:
        lines.append(_markdown_table(payload if isinstance(payload, dict) else {"value": payload}))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _markdown_table(row: Mapping[str, Any]) -> str:
    """
    Return a two-column Markdown table.

    Parameters:
        row (Mapping[str, Any]): Field names and values.

    Returns:
        str: Markdown table. Nested lists and objects are JSON.
    """
    lines = ["| field | value |", "| --- | --- |"]
    for key, value in row.items():
        if isinstance(value, (dict, list)):
            rendered = json.dumps(value, ensure_ascii=False)
        elif value is None:
            rendered = ""
        else:
            rendered = str(value)
        escaped = rendered.replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {key} | {escaped} |")
    return "\n".join(lines)


def _flatten(row: Mapping[str, Any]) -> dict[str, Any]:
    """
    Return a flat row, encoding nested values as JSON.

    Parameters:
        row (Mapping[str, Any]): Source row.

    Returns:
        dict[str, Any]: Scalar values. Nested values are JSON strings.
    """
    flat: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (dict, list)):
            flat[key] = json.dumps(value, ensure_ascii=False)
        elif value is None:
            flat[key] = ""
        else:
            flat[key] = value
    return flat


def _csv_rows(payload: Any) -> list[dict[str, Any]]:
    """
    Return CSV rows for a snapshot or a history list.

    Parameters:
        payload (Any): Latest document or history rows.

    Returns:
        list[dict[str, Any]]: One flat row per channel or history row.
    """
    if isinstance(payload, dict) and isinstance(payload.get("channels"), dict):
        rows: list[dict[str, Any]] = []
        for name, body in payload["channels"].items():
            row = {"channel": name, "updated_at": payload.get("updated_at", "")}
            if isinstance(body, dict):
                row.update(_flatten(body))
            rows.append(row)
        return rows
    if isinstance(payload, list):
        return [_flatten(row) if isinstance(row, dict) else {"value": row} for row in payload]
    if isinstance(payload, dict):
        return [_flatten(payload)]
    return [{"value": payload}]


def _csv_text(payload: Any) -> str:
    """
    Return CSV text for ``payload``.

    Parameters:
        payload (Any): Latest document or history rows.

    Returns:
        str: CSV text ending in a newline. Header only when there are no rows.
    """
    rows = _csv_rows(payload)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames or ["value"])
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def _toml_scalar(value: Any) -> str:
    """
    Return one TOML scalar.

    Parameters:
        value (Any): Scalar, list, or None.

    Returns:
        str: TOML literal. None is an empty string.
    """
    if value is None:
        return '""'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_scalar(item) for item in value) + "]"
    return json.dumps(str(value), ensure_ascii=False)


def _toml_text(payload: Any) -> str:
    """
    Return TOML text for a dict or a list of rows.

    Parameters:
        payload (Any): Latest document, history rows, or one object.

    Returns:
        str: TOML text ending in a newline.
    """
    lines: list[str] = []
    if isinstance(payload, list):
        for row in payload:
            lines.append("[[rows]]")
            _toml_table(row if isinstance(row, dict) else {"value": row}, lines)
            lines.append("")
    else:
        body = payload if isinstance(payload, dict) else {"value": payload}
        _toml_table(body, lines, prefix="")
    return "\n".join(lines).rstrip() + "\n"


def _toml_table(table: Mapping[str, Any], lines: list[str], prefix: str = "") -> None:
    """
    Append one TOML table.

    Parameters:
        table (Mapping[str, Any]): Keys and values.
        lines (list[str]): Output lines.
        prefix (str): Parent table path.
    """
    nested: list[tuple[str, Any]] = []
    for key, value in table.items():
        if isinstance(value, dict) or (isinstance(value, list) and _dicts(value)):
            nested.append((key, value))
        else:
            lines.append(f"{key} = {_toml_scalar(value)}")
    for key, value in nested:
        path = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, list):
            for item in value:
                lines.append("")
                lines.append(f"[[{path}]]")
                _toml_table(item, lines)
        else:
            lines.append("")
            lines.append(f"[{path}]")
            _toml_table(value, lines, path)


def _dicts(value: list[Any]) -> bool:
    """
    Return whether every item in ``value`` is a dict.

    Parameters:
        value (list[Any]): Candidate list.

    Returns:
        bool: True when ``value`` is a non-empty list of dicts.
    """
    return bool(value) and all(isinstance(item, dict) for item in value)


def _yaml_scalar(value: Any) -> str:
    """
    Return one YAML scalar.

    Parameters:
        value (Any): Scalar or None.

    Returns:
        str: YAML literal. None is ``null``.
    """
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def _yaml_text(payload: Any, indent: int = 0) -> str:
    """
    Return YAML text.

    Parameters:
        payload (Any): Value to encode.
        indent (int): Current indent level.

    Returns:
        str: YAML text. The top-level call ends in a newline.
    """
    pad = "  " * indent
    if isinstance(payload, dict):
        if not payload:
            text = "{}"
        else:
            lines: list[str] = []
            for key, value in payload.items():
                if isinstance(value, (dict, list)) and value:
                    lines.append(f"{pad}{key}:")
                    lines.append(_yaml_text(value, indent + 1))
                else:
                    rendered = _yaml_scalar(value) if not isinstance(value, (dict, list)) else "[]"
                    if value == {}:
                        rendered = "{}"
                    lines.append(f"{pad}{key}: {rendered}")
            text = "\n".join(lines)
    elif isinstance(payload, list):
        if not payload:
            text = "[]"
        else:
            lines = []
            for item in payload:
                if isinstance(item, dict):
                    lines.append(f"{pad}-")
                    lines.append(_yaml_text(item, indent + 1))
                else:
                    lines.append(f"{pad}- {_yaml_scalar(item)}")
            text = "\n".join(lines)
    else:
        text = f"{pad}{_yaml_scalar(payload)}"
    if indent == 0 and not text.endswith("\n"):
        return text + "\n"
    return text


def _write_payload(path: Path, payload: Any, fmt: str, settings: Settings, title: str) -> None:
    """
    Write one payload in ``fmt``.

    Parameters:
        path (Path): Destination file.
        payload (Any): Latest document or history rows.
        fmt (str): ``json``, ``md``, ``csv``, ``toml``, or ``yaml``.
        settings (Settings): JSON options.
        title (str): Markdown heading.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "json":
        path.write_bytes(_json_bytes(payload, settings))
        return
    if fmt == "md":
        text = _markdown(payload, title)
    elif fmt == "csv":
        text = _csv_text(payload)
    elif fmt == "toml":
        text = _toml_text(payload)
    else:
        text = _yaml_text(payload)
    path.write_text(text, encoding="utf-8")


def write_data_files(
    data_dir: Path,
    surfaces: list[ClientSurface],
    scraped_at: datetime | None = None,
    settings: Settings | None = None,
) -> list[Path]:
    """
    Write the snapshot and the history log.

    ``latest_formats`` chooses the snapshot files. An empty list uses
    ``output_formats``. History uses ``output_formats``.

    The JSON history file is the append log. It is updated even when ``json``
    is not one of the output formats, so later runs can still see old rows.

    Parameters:
        data_dir (Path): Directory used when a format's directory is unset.
        surfaces (list[ClientSurface]): Surfaces from this run.
        scraped_at (datetime | None): Timestamp stored on new rows.
        settings (Settings | None): Formats, paths, and fields. Defaults to
            ``Settings()``.

    Returns:
        list[Path]: Files that were written.

    Raises:
        TypeError: The JSON history file exists and is not an array.
    """
    settings = settings or Settings()
    latest_dir = Path(settings.latest_dir) if settings.latest_dir else data_dir
    history_dir = Path(settings.history_dir) if settings.history_dir else data_dir
    history_path = history_dir / f"{settings.history_filename}.json"
    history = load_json(history_path, [])
    if not isinstance(history, list):
        raise TypeError(f"{history_path} must contain a JSON array")
    latest, merged = merge_history(history, surfaces, scraped_at=scraped_at, settings=settings)
    written: list[Path] = []
    latest_formats = list(dict.fromkeys(settings.latest_formats or settings.output_formats))
    history_formats = list(dict.fromkeys(settings.output_formats))
    if "json" not in history_formats:
        history_formats.append("json")
    for fmt in latest_formats:
        extension = _EXTENSIONS[fmt]
        latest_path = latest_dir / f"{settings.latest_filename}.{extension}"
        _write_payload(latest_path, latest, fmt, settings, "latest")
        written.append(latest_path)
    for fmt in history_formats:
        extension = _EXTENSIONS[fmt]
        row_path = history_dir / f"{settings.history_filename}.{extension}"
        _write_payload(row_path, merged, fmt, settings, "history")
        written.append(row_path)
    return written
