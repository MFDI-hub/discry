from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from discry.extract import (
    assemble_surface,
    extract_capabilities,
    extract_client_build_numbers,
    parse_global_env,
    partition_scripts,
    script_paths,
)

HASH = "a" * 40
HTML = f"""
<script>window.GLOBAL_ENV = {{
  "BUILD_NUMBER":"679963",
  "VERSION_HASH":"{HASH}",
  "BUILT_AT":"1795508441085",
  "RELEASE_CHANNEL":"stable",
  "API_VERSION":9,
  "HTML_TIMESTAMP":Date.now(),
  "GATEWAY_ENDPOINT":"wss://gateway.discord.gg",
  "API_ENDPOINT":"//discord.com/api",
  "REMOTE_AUTH_ENDPOINT":"wss://remote-auth-gateway.discord.gg",
  "CDN_HOST":"cdn.discordapp.com",
  "MEDIA_PROXY_ENDPOINT":"//media.discordapp.net",
  "IMAGE_PROXY_ENDPOINTS":"//images-ext-1.discordapp.net,//images-ext-2.discordapp.net",
  "RTC_LATENCY_ENDPOINT":"//latency.discord.media/rtc",
  "NETWORKING_ENDPOINT":"//router.discordapp.net",
  "INVITE_HOST":"discord.gg",
  "GIFT_CODE_HOST":"discord.gift",
  "GUILD_TEMPLATE_HOST":"discord.new",
  "ACTIVITY_APPLICATION_HOST":"discordsays.com",
  "SEO_ENDPOINT":"undefined",
  "STRIPE_KEY":"pk_test_example",
  "ADYEN_KEY":"live_TEST",
  "BRAINTREE_KEY":"production_test_key",
  "SENTRY_TAGS":{{"buildId":"{HASH}","buildType":"normal"}},
  "SENTRY_RELEASE":"2026-11-24-{HASH}-discord_web"
}}</script>
<link rel="preload" href="/assets/web.0123abcd0123abcd.js" as="script">
<script src="/assets/fast-connect.fedcba9876543210.js"></script>
<script src="/assets/fast-connect.fedcba9876543210.js"></script>
<script>var n=null!=window.DiscordNative?"etf":"json";
o=window.GLOBAL_ENV.GATEWAY_ENDPOINT+"/?encoding="+n+"&v="+window.GLOBAL_ENV.API_VERSION;
o+="&compress=zstd-stream";o+="&compress=zlib-stream";</script>
"""


def test_global_env_accepts_date_now_and_ignores_undefined() -> None:
    env = parse_global_env(HTML)
    assert env["BUILD_NUMBER"] == "679963"
    assert env["API_VERSION"] == 9
    assert env["HTML_TIMESTAMP"] is None
    assert "SEO_ENDPOINT" not in env or env["SEO_ENDPOINT"] in {None, "undefined"}


def test_assemble_reads_the_bootstrap_page() -> None:
    surface = assemble_surface(
        channel="stable",
        html=HTML,
        headers={"x-build-id": HASH, "Last-Modified": "Tue, 24 Nov 2026 00:00:00 GMT"},
        scraped_at=datetime(2026, 11, 24, tzinfo=timezone.utc),
    )
    assert surface.build_number == 679963
    assert surface.version_hash == HASH
    assert surface.build_id == HASH
    assert surface.api_version == 9
    assert surface.gateway_endpoint == "wss://gateway.discord.gg"
    assert surface.release_channel == "stable"
    assert surface.stripe_key == "pk_test_example"
    assert surface.last_modified == "Tue, 24 Nov 2026 00:00:00 GMT"
    assert {asset.name for asset in surface.assets} == {"web", "fast-connect"}
    assert "json" in surface.gateway_encoding
    assert "etf" in surface.gateway_encoding
    assert surface.gateway_compress == ("zstd-stream", "zlib-stream")


def test_broken_object_still_yields_build_number() -> None:
    html = '<script>window.GLOBAL_ENV = {"BUILD_NUMBER":"700001","VERSION_HASH":"' + HASH + '"'
    surface = assemble_surface(channel="canary", html=html, headers={"x-build-id": "b" * 40})
    assert surface.build_number == 700001
    assert surface.version_hash == HASH
    assert surface.build_id == "b" * 40
    assert surface.release_channel == "canary"


def test_camel_case_build_number_and_header_hash() -> None:
    html = '<script>window.GLOBAL_ENV = {"buildNumber":"42","releaseChannel":"ptb-canary"}</script>'
    surface = assemble_surface(channel="ptb", html=html, headers={"X-Build-Id": "c" * 40})
    assert surface.build_number == 42
    assert surface.version_hash == "c" * 40
    assert surface.release_channel == "ptb"


def test_capabilities_literal_and_branch() -> None:
    literal = "d={token:e,capabilities:1767421,properties:o}"
    primary, values = extract_capabilities(literal)
    assert primary == 1767421
    assert values == (1767421,)

    branch = (
        "capabilities:function(e){let{useChannelObfuscation:t}=e;return t?1767421:1734653}"
        "({useChannelObfuscation:null!=n.get('private_channel_obfuscation')})"
    )
    primary, values = extract_capabilities(branch)
    assert primary == 1767421
    assert values == (1734653, 1767421)


def test_client_build_number_from_parseint_before_the_name() -> None:
    script = 'isNaN(I=parseInt("679963",10))||(s.client_build_number=I)'
    assert extract_client_build_numbers(script) == (679963,)
    surface = assemble_surface(channel="stable", html=HTML, scripts=[script])
    assert surface.client_build_number == 679963
    assert surface.capabilities is None


def test_script_order_prefers_entry_chunks() -> None:
    paths = script_paths(HTML + '<script src="/assets/999.aaaaaaaaaaaaaaaa.js"></script>')
    priority, rest = partition_scripts(paths)
    assert priority[0].startswith("/assets/fast-connect.")
    assert any(path.startswith("/assets/web.") for path in priority)
    assert rest == ["/assets/999.aaaaaaaaaaaaaaaa.js"]


def test_sentry_release_fills_a_missing_version_hash() -> None:
    html = (
        '<script>window.GLOBAL_ENV = {"BUILD_NUMBER":"1",'
        f'"SENTRY_RELEASE":"2026-11-24-{HASH}-discord_web"}}</script>'
    )
    surface = assemble_surface(channel="stable", html=html)
    assert surface.version_hash == HASH
    assert surface.build_id == HASH


def test_local_client_dump_if_present() -> None:
    html_path = Path(
        os.environ.get(
            "DISCORD_CLIENT_HTML",
            r"C:\Users\DELL\github\discordy\outputs\client\html\app.html",
        )
    )
    script_path = Path(
        os.environ.get(
            "DISCORD_CLIENT_FAST_CONNECT",
            r"C:\Users\DELL\github\discordy\outputs\client\assets\discord.com\assets"
            r"\fast-connect.932acd28174f19c9.js",
        )
    )
    if not html_path.is_file():
        return
    html = html_path.read_text(encoding="utf-8", errors="ignore")
    scripts = []
    if script_path.is_file():
        scripts.append(script_path.read_text(encoding="utf-8", errors="ignore"))
    surface = assemble_surface(channel="stable", html=html, scripts=scripts)
    assert surface.build_number == 679963
    assert surface.version_hash == "62fef5afcde85e37086b78b4e89202eaf30d447f"
    assert surface.gateway_endpoint == "wss://gateway.discord.gg"
    assert "json" in surface.gateway_encoding
    assert "zlib-stream" in surface.gateway_compress
    assert surface.assets
    if scripts:
        assert surface.capabilities == 1767421
        assert surface.client_build_number == 679963
