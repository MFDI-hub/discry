from __future__ import annotations

from discry.config import Settings
from discry.http_client import request_get


def test_request_get_sends_proxy_timeout_and_merged_headers(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_get(url: str, **kwargs: object) -> str:
        captured["url"] = url
        captured["kwargs"] = kwargs
        return "ok"

    monkeypatch.setattr("discry.http_client.requests.get", fake_get)
    settings = Settings(
        proxy="http://127.0.0.1:9",
        headers={"User-Agent": "discry"},
        timeout=5,
        verify=False,
        impersonate="chrome",
    )
    assert request_get("https://discord.com/app", settings, headers={"Accept": "text/html"}) == "ok"
    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["proxies"] == {"http": "http://127.0.0.1:9", "https": "http://127.0.0.1:9"}
    assert kwargs["timeout"] == 5
    assert kwargs["verify"] is False
    assert kwargs["impersonate"] == "chrome"
    assert kwargs["headers"]["User-Agent"] == "discry"
    assert kwargs["headers"]["Accept"] == "text/html"


def test_request_get_without_proxy_leaves_proxies_unset(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_get(url: str, **kwargs: object) -> str:
        del url
        captured["kwargs"] = kwargs
        return "ok"

    monkeypatch.setattr("discry.http_client.requests.get", fake_get)
    assert request_get("https://discord.com/app", Settings()) == "ok"
    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    assert "proxies" not in kwargs


def test_main_module_exposes_cli() -> None:
    from discry.__main__ import main

    assert callable(main)
