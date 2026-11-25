"""HTTP GET through curl_cffi so Discord receives a browser TLS fingerprint."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Protocol
from urllib.parse import urlparse

from curl_cffi import requests

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .config import Settings


class HttpResponse(Protocol):
    """
    Response fields the scraper and snapshot reader use.

    Attributes:
        ok (bool): True when the status code is below 400.
        status_code (int): HTTP status code.
        text (str): Decoded body.
        content (bytes): Raw body.
        headers (Mapping[str, str | None]): Response headers. A missing value is None.
    """

    __slots__ = ()

    @property
    def ok(self) -> bool: ...

    @property
    def status_code(self) -> int: ...

    @property
    def text(self) -> str: ...

    @property
    def content(self) -> bytes: ...

    @property
    def headers(self) -> Mapping[str, str | None]: ...


def _proxy_bypassed(url: str, no_proxy: str | None) -> bool:
    """
    Return whether ``url`` matches a ``no_proxy`` host.

    Parameters:
        url (str): Absolute URL.
        no_proxy (str | None): Comma-separated hosts. ``*`` matches every host.

    Returns:
        bool: True when the proxy should be skipped.
    """
    if not no_proxy:
        return False
    host = (urlparse(url).hostname or "").lower()
    for item in no_proxy.split(","):
        rule = item.strip().lower()
        if not rule:
            continue
        if rule == "*" or host == rule or host.endswith(f".{rule.lstrip('.')}"):
            return True
    return False


def _proxy_dict(url: str, settings: Settings) -> dict[str, str] | None:
    """
    Return the proxy map curl_cffi expects.

    Parameters:
        url (str): Absolute URL, used for ``no_proxy``.
        settings (Settings): Active settings.

    Returns:
        dict[str, str] | None: HTTP and HTTPS proxy URLs, or None when unset
        or bypassed.
    """
    if _proxy_bypassed(url, settings.no_proxy):
        return None
    http_url = settings.http_proxy or settings.proxy
    https_url = settings.https_proxy or settings.proxy
    proxies: dict[str, str] = {}
    if http_url:
        proxies["http"] = http_url
    if https_url:
        proxies["https"] = https_url
    return proxies or None


def _request_kwargs(url: str, settings: Settings, kwargs: dict[str, Any]) -> dict[str, Any]:
    """
    Fill curl_cffi arguments from ``settings``.

    Parameters:
        url (str): Absolute URL.
        settings (Settings): Active settings.
        kwargs (dict[str, Any]): Caller arguments. Explicit values win, except
            ``headers``, which are merged, and ``curl_options``, which are
            applied last.

    Returns:
        dict[str, Any]: Arguments for ``requests.get``.
    """
    proxies = _proxy_dict(url, settings)
    if proxies is not None:
        kwargs.setdefault("proxies", proxies)
    if settings.connect_timeout is None:
        kwargs.setdefault("timeout", settings.timeout)
    else:
        kwargs.setdefault("timeout", (settings.connect_timeout, settings.timeout))
    kwargs.setdefault("impersonate", settings.impersonate)
    kwargs.setdefault("verify", settings.verify)
    kwargs.setdefault("max_redirects", settings.max_redirects)
    if settings.cookies:
        kwargs.setdefault("cookies", dict(settings.cookies))
    if settings.http2 is not None:
        from curl_cffi.const import CurlHttpVersion

        kwargs.setdefault(
            "http_version",
            CurlHttpVersion.V2_0 if settings.http2 else CurlHttpVersion.V1_1,
        )
    if settings.headers:
        headers = dict(settings.headers)
        headers.update(kwargs.pop("headers", {}) or {})
        kwargs["headers"] = headers
    kwargs.update(settings.curl_options)
    return kwargs


def request_get(url: str, settings: Settings, **kwargs: Any) -> HttpResponse:
    """
    Fetch one URL with the configured browser fingerprint.

    Connection failures propagate from curl_cffi after the configured retries.
    An HTTP error status stays on the response when no retries remain.

    Parameters:
        url (str): Absolute URL.
        settings (Settings): Timeout, proxy, headers, and impersonation profile.
        **kwargs (Any): Extra arguments forwarded to curl_cffi. Values already
            set from ``settings`` are left in place unless ``headers`` is passed,
            in which case those headers are merged on top.

    Returns:
        HttpResponse: Response from curl_cffi.
    """
    prepared = _request_kwargs(url, settings, kwargs)
    attempts = settings.retries + 1
    for attempt in range(attempts):
        try:
            response = requests.get(url, **prepared)
        except Exception:
            if attempt + 1 >= attempts:
                raise
        else:
            if getattr(response, "ok", True) or attempt + 1 >= attempts:
                return response
        if settings.retry_backoff > 0:
            time.sleep(settings.retry_backoff * (attempt + 1))
    raise RuntimeError(f"Failed to fetch {url}")
