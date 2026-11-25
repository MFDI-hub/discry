"""Command line for discry."""

from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

from .config import DEFAULT_LOG_FORMAT, load_settings, resolve_moment
from .enums import ExitCode
from .history import write_data_files
from .latest import fetch_latest
from .scraper import scrape_channels

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """
    Parse command-line arguments.

    Parameters:
        argv (list[str] | None): Arguments without the program name. Defaults
            to the process arguments.

    Returns:
        argparse.Namespace: Parsed flags.
    """
    parser = argparse.ArgumentParser(description="Scrape Discord web client bootstrap values")
    parser.add_argument("--config", help="Path to config.toml (default: ./config.toml if present)")
    parser.add_argument(
        "--set",
        action="append",
        metavar="KEY=VALUE",
        help="Override any setting. Repeatable. Lists are comma-separated. Tables are JSON.",
    )
    parser.add_argument("--impersonate", help="curl_cffi browser profile, for example chrome")
    parser.add_argument("--proxy", help="Proxy URL, for example socks5://user:pass@host:port")
    parser.add_argument("--timeout", type=float, help="HTTP timeout in seconds")
    parser.add_argument("--no-verify", action="store_true", help="Disable TLS certificate verify")
    parser.add_argument(
        "--channel",
        action="append",
        dest="channels",
        help="Channel to scrape (repeatable). Defaults to config channels.",
    )
    parser.add_argument(
        "--data-dir",
        help="Directory for the snapshot and history files",
    )
    parser.add_argument("--max-files", type=int, help="Max JS files to inspect per channel")
    parser.add_argument("--concurrency", type=int, help="Parallel download limit")
    parser.add_argument(
        "--asset-base-url",
        help="Base URL for /assets/ files. Defaults to the channel host.",
    )
    parser.add_argument(
        "--from-repo",
        action="store_true",
        help="Fetch the published snapshot instead of scraping Discord",
    )
    parser.add_argument(
        "--latest-url",
        help="Snapshot URL. GitHub blob URLs are converted to raw.",
    )
    parser.add_argument(
        "--output-format",
        action="append",
        dest="output_formats",
        choices=("json", "md", "markdown", "csv", "toml", "yaml", "yml"),
        help="Output format. Repeatable. Defaults to json.",
    )
    parser.add_argument("--timezone", help="UTC, local, +HH:MM, or an IANA name")
    parser.add_argument("--timestamp-format", help="iso, or a strftime pattern")
    parser.add_argument("--scraped-at", help="Timestamp to store instead of the current time")
    parser.add_argument("--log-level", help="DEBUG, INFO, WARNING, ERROR, or CRITICAL")
    parser.add_argument("--log-file", help="Write logs to this file")
    parser.add_argument(
        "--write-on-fetch",
        action="store_true",
        help="Write output files when reading a published snapshot",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser.parse_args(argv)


def _set_overrides(items: list[str]) -> dict[str, Any]:
    """
    Parse ``--set key=value`` flags.

    Parameters:
        items (list[str]): Raw ``key=value`` strings.

    Returns:
        dict[str, Any]: Setting names and raw values.

    Raises:
        ValueError: An item has no equals sign.
    """
    raw: dict[str, Any] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"Expected key=value, got {item!r}")
        key, value = item.split("=", 1)
        raw[key.strip()] = value.strip()
    return raw


def main(argv: list[str] | None = None) -> ExitCode:
    """
    Scrape Discord, or read a published snapshot.

    Parameters:
        argv (list[str] | None): Arguments without the program name.

    Returns:
        ExitCode: ``SUCCESS`` when the run finishes, otherwise ``FAILURE``.
    """
    args = parse_args(argv)
    try:
        overrides = _set_overrides(args.set or [])
        explicit = {
            "impersonate": args.impersonate,
            "proxy": args.proxy,
            "timeout": args.timeout,
            "verify": False if args.no_verify else None,
            "channels": tuple(args.channels) if args.channels else None,
            "data_dir": args.data_dir,
            "max_files": args.max_files,
            "download_concurrency": args.concurrency,
            "asset_base_url": args.asset_base_url,
            "latest_url": args.latest_url,
            "output_formats": tuple(args.output_formats) if args.output_formats else None,
            "timezone": args.timezone,
            "timestamp_format": args.timestamp_format,
            "scraped_at": args.scraped_at,
            "log_level": args.log_level,
            "log_file": args.log_file,
            "from_repo": True if args.from_repo else None,
            "write_on_fetch": True if args.write_on_fetch else None,
        }
        overrides.update({key: value for key, value in explicit.items() if value is not None})
        settings = load_settings(config_path=args.config, overrides=overrides)
    except Exception as exc:
        logging.basicConfig(
            level=logging.DEBUG if args.verbose else logging.INFO,
            format=DEFAULT_LOG_FORMAT,
        )
        logger.error("Invalid configuration: %s", exc)
        return ExitCode.FAILURE
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else getattr(logging, settings.log_level.upper()),
        format=settings.log_format,
        filename=settings.log_file,
    )

    moment = resolve_moment(settings)
    if settings.from_repo:
        try:
            latest = fetch_latest(url=settings.latest_url, settings=settings)
            surfaces = [latest[name] for name in settings.channels]
        except Exception as exc:
            logger.error("Fetch failed: %s", exc)
            return ExitCode.FAILURE
        if settings.write_on_fetch:
            write_data_files(
                Path(settings.data_dir), surfaces, scraped_at=moment, settings=settings
            )
    else:
        logger.info(
            "Scraping %s with impersonate=%s",
            ",".join(settings.channels),
            settings.impersonate,
        )
        try:
            surfaces = asyncio.run(scrape_channels(settings=settings, scraped_at=moment))
        except Exception as exc:
            logger.error("Scrape failed: %s", exc)
            return ExitCode.FAILURE
        if settings.write_output:
            write_data_files(
                Path(settings.data_dir), surfaces, scraped_at=moment, settings=settings
            )

    for surface in surfaces:
        logger.info(
            "%s build_number=%s version_hash=%s capabilities=%s",
            surface.channel,
            surface.build_number,
            surface.version_hash,
            surface.capabilities,
        )
    return ExitCode.SUCCESS
