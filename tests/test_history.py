from __future__ import annotations

from datetime import datetime, timezone

import orjson

from discry.config import Settings
from discry.history import history_key, merge_history, write_data_files
from discry.models import ClientSurface


def _surface(build: int = 1, capabilities: int | None = 5) -> ClientSurface:
    return ClientSurface(
        channel="stable",
        build_number=build,
        version_hash="a" * 40,
        capabilities=capabilities,
        release_channel="stable",
    )


def test_history_appends_once_and_again_when_capabilities_change(tmp_path) -> None:
    when = datetime(2026, 1, 1, tzinfo=timezone.utc)
    latest, history = merge_history([], [_surface()], scraped_at=when)
    assert latest["channels"]["stable"]["build_number"] == 1
    again, history = merge_history(history, [_surface()], scraped_at=when)
    assert len(history) == 1
    assert again["updated_at"] == when.isoformat()
    _, history = merge_history(history, [_surface(capabilities=9)], scraped_at=when)
    assert len(history) == 2
    assert history_key(history[0]) != history_key(history[1])


def test_write_data_files_round_trip(tmp_path) -> None:
    write_data_files(tmp_path, [_surface()], scraped_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    write_data_files(tmp_path, [_surface()], scraped_at=datetime(2026, 1, 3, tzinfo=timezone.utc))
    history = (tmp_path / "history.json").read_bytes()
    assert history.count(b'"channel": "stable"') == 1
    assert b'"build_number": 1' in (tmp_path / "latest.json").read_bytes()


def test_latest_formats_leave_history_as_json(tmp_path) -> None:
    settings = Settings(latest_formats=("json", "md", "csv", "toml", "yaml")).validate()
    write_data_files(
        tmp_path,
        [_surface()],
        scraped_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        settings=settings,
    )
    for name in (
        "latest.json",
        "latest.md",
        "latest.csv",
        "latest.toml",
        "latest.yaml",
        "history.json",
    ):
        assert (tmp_path / name).is_file()
    assert not (tmp_path / "history.md").exists()


def test_extra_formats_and_timestamp_pattern(tmp_path) -> None:
    settings = Settings(
        output_formats=("json", "md", "csv"),
        timestamp_format="%Y%m%d",
        timezone="UTC",
    ).validate()
    write_data_files(
        tmp_path,
        [_surface()],
        scraped_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
        settings=settings,
    )
    assert "20260102" in (tmp_path / "latest.md").read_text(encoding="utf-8")
    assert "stable" in (tmp_path / "history.csv").read_text(encoding="utf-8")
    assert b"20260102" in (tmp_path / "latest.json").read_bytes()


def test_history_rolls_to_a_timestamped_file(tmp_path) -> None:
    first = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    settings = Settings(output_formats=("json", "md")).validate()
    write_data_files(tmp_path, [_surface(1)], scraped_at=first, settings=settings)
    largest = max(
        path.stat().st_size for path in (tmp_path / "history.json", tmp_path / "history.md")
    )
    tight = Settings(history_rotate_bytes=largest + 1, output_formats=("json", "md")).validate()
    closed_at = datetime(2026, 6, 7, 8, 9, 10, tzinfo=timezone.utc)
    write_data_files(tmp_path, [_surface(2)], scraped_at=closed_at, settings=tight)

    archives = sorted(tmp_path.glob("history-*.json"))
    assert [path.name for path in archives] == ["history-2026-06-07T08-09-10Z.json"]
    old = orjson.loads(archives[0].read_bytes())
    current = orjson.loads((tmp_path / "history.json").read_bytes())
    assert [row["build_number"] for row in old] == [1]
    assert [row["build_number"] for row in current] == [2]
    assert "| build_number | 1 |" in (tmp_path / "history-2026-06-07T08-09-10Z.md").read_text(
        encoding="utf-8"
    )
    assert "| build_number | 2 |" in (tmp_path / "history.md").read_text(encoding="utf-8")

    write_data_files(tmp_path, [_surface(1), _surface(2)], scraped_at=closed_at, settings=tight)
    current = orjson.loads((tmp_path / "history.json").read_bytes())
    assert [row["build_number"] for row in current] == [2]
    assert len(list(tmp_path.glob("history-*.json"))) == 1
