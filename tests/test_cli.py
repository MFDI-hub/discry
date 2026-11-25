from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from discry.cli import main
from discry.latest import LatestSurfaces
from discry.models import ClientSurface
from discry.scraper import SurfaceNotFoundError

if TYPE_CHECKING:
    import pytest


def test_main_scrape_writes_data(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    surface = ClientSurface(channel="stable", build_number=4, version_hash="e" * 40, capabilities=7)

    async def fake_scrape(**kwargs):
        assert kwargs["settings"].channels == ("stable",)
        return [surface]

    written: list[ClientSurface] = []

    def fake_write(data_dir, surfaces, scraped_at=None, settings=None):
        del scraped_at, settings
        written.extend(surfaces)
        return [data_dir / "latest.json", data_dir / "history.json"]

    monkeypatch.setattr("discry.cli.scrape_channels", fake_scrape)
    monkeypatch.setattr("discry.cli.write_data_files", fake_write)
    assert (
        main(
            [
                "--channel",
                "stable",
                "--data-dir",
                str(tmp_path),
                "--config",
                str(tmp_path / "missing"),
            ]
        )
        == 1
    )

    config = tmp_path / "config.toml"
    config.write_text('channels = ["stable"]\n', encoding="utf-8")
    assert main(["--channel", "stable", "--data-dir", str(tmp_path), "--config", str(config)]) == 0
    assert written == [surface]


def test_main_reports_scrape_and_fetch_failures(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    config = tmp_path / "config.toml"
    config.write_text('channels = ["stable"]\n', encoding="utf-8")

    async def boom(**kwargs):
        del kwargs
        raise SurfaceNotFoundError("down")

    monkeypatch.setattr("discry.cli.scrape_channels", boom)
    assert main(["--config", str(config), "--data-dir", str(tmp_path)]) == 1

    def fake_fetch(url, settings):
        del url, settings
        raise SurfaceNotFoundError("missing")

    monkeypatch.setattr("discry.cli.fetch_latest", fake_fetch)
    assert main(["--from-repo", "--config", str(config)]) == 1


def test_main_from_repo(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    config = tmp_path / "config.toml"
    config.write_text('channels = ["stable"]\n', encoding="utf-8")
    surface = ClientSurface(
        channel="stable",
        build_number=9,
        version_hash="f" * 40,
        capabilities=1,
        scraped_at=datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat(),
    )

    def fake_fetch(url, settings):
        del url
        return LatestSurfaces(updated_at="t", channels={"stable": surface}, source_url="mem")

    monkeypatch.setattr("discry.cli.fetch_latest", fake_fetch)
    assert main(["--from-repo", "--config", str(config)]) == 0


def test_main_rejects_bad_timeout(tmp_path) -> None:
    config = tmp_path / "config.toml"
    config.write_text('channels = ["stable"]\n', encoding="utf-8")
    assert main(["--config", str(config), "--timeout", "0"]) == 1
