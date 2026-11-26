from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from discry.client_code import ChannelCapture, logical_script_name, write_client_files
from discry.config import Settings
from discry.models import ClientSurface
from discry.scraper import capture_channel

if TYPE_CHECKING:
    import pytest


def _surface(channel: str = "stable") -> ClientSurface:
    return ClientSurface(channel=channel, build_number=1, version_hash="a" * 40)


def test_logical_script_name_drops_the_content_hash() -> None:
    settings = Settings()
    assert logical_script_name("/assets/web.0123abcd0123abcd.js", settings) == "web.js"
    assert logical_script_name("/assets/fast-connect.0123456789abcdef.js", settings) == (
        "fast-connect.js"
    )


def test_write_client_files_replaces_changes_and_drops_stale_files(tmp_path) -> None:
    settings = Settings()
    page = "<html>one</html>"
    scripts = (("/assets/web.0123abcd0123abcd.js", "var build = 1;\n"),)
    write_client_files(
        tmp_path,
        [ChannelCapture(surface=_surface(), page=page, scripts=scripts)],
        settings,
    )
    web = tmp_path / "client" / "stable" / "web.js"
    assert web.read_text(encoding="utf-8") == "var build = 1;\n"
    assert (tmp_path / "client" / "stable" / "app.html").read_text(encoding="utf-8") == page
    stamp = web.stat().st_mtime_ns
    (tmp_path / "client" / "stable" / "old.js").write_text("gone", encoding="utf-8")

    write_client_files(
        tmp_path,
        [ChannelCapture(surface=_surface(), page=page, scripts=scripts)],
        settings,
    )
    assert web.stat().st_mtime_ns == stamp
    assert not (tmp_path / "client" / "stable" / "old.js").exists()

    write_client_files(
        tmp_path,
        [
            ChannelCapture(
                surface=_surface(),
                page=page,
                scripts=(("/assets/web.ffffffffffffffff.js", "var build = 2;\n"),),
            )
        ],
        settings,
    )
    assert web.read_text(encoding="utf-8") == "var build = 2;\n"
    assert list(tmp_path.glob("client/stable/*.js")) == [web]


def test_save_client_false_writes_nothing(tmp_path) -> None:
    settings = Settings(save_client=False).validate()
    written = write_client_files(
        tmp_path,
        [ChannelCapture(surface=_surface(), page="<html></html>", scripts=())],
        settings,
    )
    assert written == []
    assert not (tmp_path / "client").exists()


def test_capture_still_downloads_scripts_when_the_page_is_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []
    html = (
        "<script>window.GLOBAL_ENV = {"
        '"BUILD_NUMBER":"12","VERSION_HASH":"' + ("d" * 40) + '","RELEASE_CHANNEL":"stable"'
        "}</script>"
        "capabilities:1767421,client_build_number:10012"
        '<script src="/assets/web.0123456789abcdef.js"></script>'
    )

    class Response:
        def __init__(self, text: str) -> None:
            self.text = text
            self.status_code = 200
            self.ok = True
            self.headers: dict[str, str] = {}

    def fake_get(url: str, settings: Settings) -> Response:
        del settings
        seen.append(url)
        if url.endswith("/app"):
            return Response(html)
        return Response("client code")

    monkeypatch.setattr("discry.scraper.request_get", fake_get)
    capture = asyncio.run(
        capture_channel(
            "stable",
            settings=Settings(save_client=True),
            scraped_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
    )
    assert capture.surface.build_number == 12
    assert capture.scripts == (("/assets/web.0123456789abcdef.js", "client code"),)
    assert seen[-1].endswith("/assets/web.0123456789abcdef.js")


def test_save_client_false_stops_once_the_surface_is_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[str] = []

    class Response:
        def __init__(self, text: str) -> None:
            self.text = text
            self.status_code = 200
            self.ok = True
            self.headers: dict[str, str] = {}

    def fake_get(url: str, settings: Settings) -> Response:
        del settings
        seen.append(url)
        if url.endswith("/app"):
            return Response(
                "<script>window.GLOBAL_ENV = {"
                '"BUILD_NUMBER":"12","VERSION_HASH":"' + ("d" * 40) + '"'
                "}</script>"
                "capabilities:1767421,client_build_number:10012"
                '<script src="/assets/web.0123456789abcdef.js"></script>'
            )
        raise AssertionError(url)

    monkeypatch.setattr("discry.scraper.request_get", fake_get)
    surface = asyncio.run(
        capture_channel("stable", settings=Settings(save_client=False).validate())
    ).surface
    assert surface.capabilities == 1767421
    assert seen == ["https://discord.com/app"]
