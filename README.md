# discry

Scrape the public Discord web client for the values that change with a build.

Fetches `https://discord.com/app` (and the PTB and canary hosts) the same way
[discord_build_number_scrapper](https://github.com/MFDI-hub/discord_build_number_scrapper)
fetches a build number. No login. A field that disappears in a later build is
left empty; the rest of the snapshot is still written.

```shell
pip install discry
discry
```

```shell
uvx --from discry discry
```

From a checkout:

```shell
pip install -e .
discry
```

```shell
uv sync
uv run discry
```

```python
from discry import fetch_latest

latest = fetch_latest()
print(latest["stable"].build_number, latest["stable"].capabilities)
```

The package runs on Python 3.8 or newer. A full development install, including
the docs, needs Python 3.11 or newer.

## Files

A local run with the defaults writes:

- `data/latest.json`, the current snapshot. `updated_at` is the run clock.
  Each channel object holds the surface, including `scraped_at`.
- `data/history.json`, an append-only log in the same role as
  `discord_build_number_scrapper`'s `data/history.json`. A row is added when
  `channel`, `build_number`, `version_hash`, or `capabilities` changes. An
  empty `version_hash` uses `build_id`.

That other history file stores `channel`, `build_number`, `build_hash`,
`build_date`, and `first_seen`. This one stores `channel`, `build_number`,
`version_hash`, `build_id`, `capabilities`, `capability_values`,
`client_build_number`, `release_channel`, `built_at`, and `first_seen`.

`latest_formats` can also write `latest.md`, `latest.csv`, `latest.toml`, and
`latest.yaml`. `output_formats` selects those formats for the history log.
`markdown` means `md`. `yml` means `yaml`. JSON indent defaults to 2. Indent
`0` is compact. The JSON history file is still updated when `json` is not a
selected history format, because later runs read it to decide which rows are
new.

The hourly GitHub workflow sets `SCRAPER_LATEST_FORMATS` to
`json,md,csv,toml,yaml` and leaves history as `data/history.json`. It commits
`data/latest.json`, `data/latest.md`, `data/latest.csv`, `data/latest.toml`,
`data/latest.yaml`, and `data/history.json`.

`--from-repo` fetches the published `latest.json` and does not write files
unless `--write-on-fetch` or `write_on_fetch = true`.

## Fields

`build_number`, `version_hash`, `build_id`, `built_at`, `last_modified`,
`release_channel`, `api_version`, `gateway_endpoint`, `api_endpoint`,
`remote_auth_endpoint`, `cdn_host`, `media_proxy_endpoint`,
`image_proxy_endpoints`, `rtc_latency_endpoint`, `networking_endpoint`,
`invite_host`, `gift_code_host`, `guild_template_host`,
`activity_application_host`, `assets`, `gateway_encoding`, `gateway_compress`,
`stripe_key`, `adyen_key`, `braintree_key`, `capabilities`,
`capability_values`, `client_build_number`, `scraped_at`.

`capabilities` is the mask the current page sends on IDENTIFY. When the client
still has a branch, `capability_values` keeps every mask from that branch.
`assets` are the content hashes linked from the app HTML (`js`, `css`, `mjs`).
`gateway_encoding` (`json`, `etf`) and `gateway_compress` (`zstd-stream`,
`zlib-stream`) are the literals the page uses for the gateway query.

`built_at` is stored as Discord sent it. `last_modified` is the raw HTTP date.
`scraped_at`, `updated_at`, and `first_seen` share one clock. The default is
`datetime.now(timezone.utc).isoformat()`, including microseconds. `timezone`
accepts `UTC`, `local`, `+HH:MM`, or an IANA name on Python 3.9+.
`timestamp_format` is `iso` or a `strftime` pattern. `scraped_at_format`,
`updated_at_format`, and `first_seen_format` override it per field.
`--scraped-at` or `scraped_at` in the config pins the instant.

## How a scrape stops

Each channel is `GET https://{host}/app`. The HTML `GLOBAL_ENV` object and the
`x-build-id` and `last-modified` headers are read first. Scripts under
`/assets/` ending in `.js` are downloaded only when the page is incomplete.
`fast-connect.`, `web.`, and `sentry.` come first. At most 40 files are
inspected, 8 at a time.

Downloads are skipped when a build identity is already present and both
`capabilities` and `client_build_number` are set. A channel succeeds when any
of `build_number`, `version_hash`, or `build_id` is present. Channels run one
at a time. One failure fails the run after the others are attempted.

## CLI

Priority is CLI flags, then `SCRAPER_*` environment variables, then
`config.toml`, then the defaults. `--set KEY=VALUE` overrides any field.
Lists are comma-separated. Tables are JSON. A dedicated flag wins over
`--set`. `-v` forces `DEBUG` for that process only.

| Flag | Description |
| --- | --- |
| `--config PATH` | `config.toml`. Default: `./config.toml` when it exists |
| `--set KEY=VALUE` | Any setting. Repeatable |
| `--channel NAME` | Channel to scrape. Repeatable. Default: stable, ptb, canary |
| `--impersonate PROFILE` | curl_cffi browser profile. Default: `chrome` |
| `--proxy URL` | Proxy URL for HTTP and HTTPS |
| `--timeout SECONDS` | HTTP timeout. Default: 30 |
| `--no-verify` | Disable TLS verification |
| `--data-dir PATH` | Output directory. Default: `data` |
| `--max-files N` | JS files to inspect per channel. Default: 40 |
| `--concurrency N` | Parallel script downloads. Default: 8 |
| `--asset-base-url URL` | Origin for `/assets/` files. Default: the channel host |
| `--output-format NAME` | History format. Repeatable. Default: `json` |
| `--timezone NAME` | `UTC`, `local`, `+HH:MM`, or an IANA name |
| `--timestamp-format PATTERN` | `iso` or a `strftime` pattern |
| `--scraped-at TEXT` | Timestamp to store instead of now |
| `--from-repo` | Read `latest.json` from GitHub instead of scraping |
| `--latest-url URL` | Snapshot URL. Blob URLs are converted to raw |
| `--write-on-fetch` | Write files after `--from-repo` |
| `--log-level LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` |
| `--log-file PATH` | Log file. Default: stderr |
| `-v`, `--verbose` | Debug logging |

Environment variables are `SCRAPER_` plus the upper-case field name.
`download_concurrency` is `SCRAPER_CONCURRENCY`. `SCRAPER_CONFIG` is the file
path. Optional strings treat `""`, `0`, `false`, `none`, and `off` as unset.
Booleans accept `1`/`true`/`yes`/`on` and `0`/`false`/`no`/`off`.

Every field, default, and environment name is in
[docs/configuration.md](docs/configuration.md). The scrape, the file formats,
and the GitHub job are in [docs/usage.md](docs/usage.md). The API reference is
built from the docstrings when the docs site is generated.
