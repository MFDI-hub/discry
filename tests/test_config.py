from pathlib import Path

import pytest

from discry.config import Settings, load_settings


def test_toml_env_and_overrides(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        'timeout = 15\nchannels = ["stable"]\nasset_base_url = ""\n\n[domains]\nstaging = "staging.discord.com"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("SCRAPER_TIMEOUT", "9")
    monkeypatch.setenv("SCRAPER_CHANNELS", "canary,staging")
    settings = load_settings(
        config_path=config,
        overrides={"max_files": 3, "impersonate": "chrome"},
    )
    assert settings.timeout == 9
    assert settings.channels == ("canary", "staging")
    assert settings.max_files == 3
    assert settings.asset_base_url is None
    assert settings.domains["staging"] == "staging.discord.com"
    assert settings.domains["stable"] == "discord.com"


def test_unknown_key_and_bad_timeout(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text("nope = 1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Unknown config"):
        load_settings(config_path=config, environ=False)
    with pytest.raises(ValueError, match="timeout"):
        Settings(timeout=0).validate()
    with pytest.raises(ValueError, match="history_rotate_bytes"):
        Settings(history_rotate_bytes=0).validate()


def test_missing_domain_is_rejected() -> None:
    with pytest.raises(ValueError, match="No domain"):
        Settings(channels=("staging",)).validate()


def test_domains_replace_drops_builtins(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        'channels = ["staging"]\ndomains_replace = true\n\n[domains]\nstaging = "staging.discord.com"\n',
        encoding="utf-8",
    )
    settings = load_settings(config_path=config, environ=False)
    assert settings.domains == {"staging": "staging.discord.com"}
    assert settings.output_formats == ("json",)
    assert settings.timezone == "UTC"
    assert settings.app_path == "/app"
    assert settings.write_on_fetch is False
