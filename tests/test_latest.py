import pytest

from discry.latest import (
    LatestFetchError,
    fetch_latest,
    parse_latest,
    to_raw_github_url,
)
from discry.models import ClientSurface


def test_blob_url_becomes_raw() -> None:
    url = "https://github.com/MFDI-hub/discry/blob/main/data/latest.json"
    assert to_raw_github_url(url) == (
        "https://raw.githubusercontent.com/MFDI-hub/discry/main/data/latest.json"
    )
    assert to_raw_github_url("https://example.com/latest.json") == "https://example.com/latest.json"


def test_parse_latest_tolerates_missing_optional_fields() -> None:
    latest = parse_latest(
        {"updated_at": "2026-01-01T00:00:00+00:00", "channels": {"stable": {"build_number": "8"}}},
        "memory",
    )
    surface = latest["stable"]
    assert surface.build_number == 8
    assert surface.capabilities is None
    assert surface.assets == ()
    with pytest.raises(KeyError):
        latest["missing"]


def test_parse_latest_rejects_a_bad_document() -> None:
    with pytest.raises(LatestFetchError):
        parse_latest([], "memory")
    with pytest.raises(LatestFetchError):
        parse_latest(
            {"updated_at": "now", "channels": {"stable": {"build_number": "nope"}}}, "memory"
        )


def test_fetch_latest_uses_the_response_body(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        ok = True
        status_code = 200
        content = (
            b'{"updated_at":"t","channels":{"canary":{"build_number":3,"gateway_encoding":"json"}}}'
        )

    def fake_get(url: str, settings: object) -> Response:
        del url, settings
        return Response()

    monkeypatch.setattr("discry.latest.request_get", fake_get)
    latest = fetch_latest("https://example.com/latest.json")
    assert latest["canary"].build_number == 3
    assert latest["canary"].gateway_encoding == ("json",)
    assert isinstance(latest["canary"], ClientSurface)
