from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from discry.config import Settings
from discry.scraper import SurfaceNotFoundError, scrape_channel, scrape_channels

HASH = "d" * 40


class Response:
    def __init__(self, text: str, status: int = 200, headers: dict[str, str] | None = None) -> None:
        self.text = text
        self.status_code = status
        self.ok = status < 400
        self.headers = headers or {}


def _html() -> str:
    return (
        "<script>window.GLOBAL_ENV = {"
        f'"BUILD_NUMBER":"12","VERSION_HASH":"{HASH}","RELEASE_CHANNEL":"stable"'
        "}</script>"
        '<script src="/assets/fast-connect.0123456789abcdef.js"></script>'
        '<script src="/assets/111.abcdefabcdefabcd.js"></script>'
    )


def test_scrape_channel_reads_html_then_entry_script(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def fake_get(url: str, settings: Settings) -> Response:
        del settings
        seen.append(url)
        if url.endswith("/app"):
            return Response(_html(), headers={"x-build-id": HASH})
        if url.endswith("fast-connect.0123456789abcdef.js"):
            return Response(
                "capabilities:1767421,properties:{};"
                'isNaN(I=parseInt("10012",10))||(s.client_build_number=I)'
            )
        raise AssertionError(url)

    monkeypatch.setattr("discry.scraper.request_get", fake_get)
    surface = asyncio.run(
        scrape_channel(
            "stable",
            settings=Settings(channels=("stable",), download_concurrency=1),
            scraped_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
    )
    assert surface.build_number == 12
    assert surface.capabilities == 1767421
    assert surface.client_build_number == 10012
    assert seen == [
        "https://discord.com/app",
        "https://discord.com/assets/fast-connect.0123456789abcdef.js",
    ]


def test_asset_download_failure_is_skipped(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, settings: Settings) -> Response:
        del settings
        if url.endswith("/app"):
            return Response(_html(), headers={"x-build-id": HASH})
        raise RuntimeError("offline")

    monkeypatch.setattr("discry.scraper.request_get", fake_get)
    surface = asyncio.run(scrape_channel("stable", settings=Settings()))
    assert surface.build_number == 12
    assert surface.capabilities is None


def test_page_without_identity_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, settings: Settings) -> Response:
        del url, settings
        return Response("<html>not discord</html>")

    monkeypatch.setattr("discry.scraper.request_get", fake_get)
    with pytest.raises(SurfaceNotFoundError):
        asyncio.run(scrape_channel("stable", settings=Settings()))


def test_http_error_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, settings: Settings) -> Response:
        del url, settings
        return Response("no", status=403)

    monkeypatch.setattr("discry.scraper.request_get", fake_get)
    with pytest.raises(SurfaceNotFoundError):
        asyncio.run(scrape_channel("ptb", settings=Settings()))


def test_one_channel_failure_fails_the_run(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, settings: Settings) -> Response:
        del settings
        if "ptb." in url:
            return Response("no", status=500)
        return Response(_html(), headers={"x-build-id": HASH})

    monkeypatch.setattr("discry.scraper.request_get", fake_get)
    with pytest.raises(SurfaceNotFoundError, match="ptb"):
        asyncio.run(scrape_channels(settings=Settings(channels=("stable", "ptb"), max_files=1)))
