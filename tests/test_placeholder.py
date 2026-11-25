"""Placeholder tests.

Delete these once you have real tests; they exist so that a freshly generated
project passes `make test` including its coverage gate.
"""

from __future__ import annotations

import discord_client_scrapper
from discord_client_scrapper import discord_client_scrapper as cli


def test_version_is_a_string() -> None:
    assert isinstance(discord_client_scrapper.__version__, str)


def test_main_runs() -> None:
    assert cli.main() is None


def test_python_m_entrypoint() -> None:
    import importlib

    entry = importlib.import_module("discord_client_scrapper.__main__")
    assert entry.main is cli.main
