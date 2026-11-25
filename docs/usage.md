# Usage

`discry` reads the public Discord web client and writes the
values that change with a build. It does not log in. A field that a later
build stops publishing is left empty. The rest of the snapshot is still written.

The same idea as
[discord_build_number_scrapper](https://github.com/MFDI-hub/discord_build_number_scrapper):
fetch the app page, keep `data/latest.json` as the current snapshot, and append
`data/history.json` when a build changes. This package stores the wider client
surface, and it can write the snapshot in more than one format.

## Run it

Without a checkout:

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

The program is also `python -m discry`. Exit code `0` means
the run finished. Exit code `1` means configuration, fetch, or scrape failed.

A local run with no extra options writes `data/latest.json` and
`data/history.json`. The hourly GitHub workflow writes the snapshot in every
format and still keeps history as JSON. See [GitHub](#github).

## What one scrape does

For each name in `channels`, in order:

1. Look up the host in `domains`. The built-in map is `stable` →
   `discord.com`, `ptb` → `ptb.discord.com`, `canary` →
   `canary.discord.com`. A channel with no domain fails validation before any
   request.
2. `GET {url_scheme}://{host}{app_path}`. The defaults are `https` and `/app`,
   so the stable URL is `https://discord.com/app`.
3. Read `GLOBAL_ENV` from the HTML, plus the response headers named by
   `build_id_header` (`x-build-id`) and `last_modified_header`
   (`last-modified`).
4. Download scripts when the page is not already complete. Script tags whose
   path starts with `asset_prefix` (`/assets/`) and whose extension is in
   `script_extensions` (`js`) are candidates. Names that start with
   `script_priority` are fetched first: `fast-connect.`, then `web.`, then
   `sentry.`. At most `max_files` (40) bodies are inspected, `download_concurrency`
   (8) at a time. A failed script is skipped and logged.
5. Require the identity fields. By default any one of `build_number`,
   `version_hash`, or `build_id` is enough. If none of them is present the
   channel fails.

Script downloads are skipped when the identity fields match and every name in
`skip_script_fields` is already set. The defaults require both `capabilities`
and `client_build_number` on top of the identity.

The remaining, non-priority scripts are added only when any name in
`rest_script_fields` is missing. The defaults are `capabilities` and
`build_number`.

Downloading stops when every name in `stop_fields` is set (`build_number` and
`capabilities`) and either every name in `stop_early_fields` is set
(`client_build_number`) or the priority scripts have already been fetched.

`channel_concurrency` is `1`, so channels run one after another. Raising it
fetches several channels at once and still returns them in request order.
`continue_on_error` is false, so one failure fails the run after the other
channels have been attempted. Set it true to return the channels that
succeeded. If every channel fails, the run still fails.

Asset file URLs are `{asset_base_url}{path}` when `asset_base_url` is set.
Otherwise they use `{url_scheme}://{host}` plus the path from the page.

## Where values come from

Each value is taken from the first source that still looks like that value.

| Field | Source |
| --- | --- |
| `build_number` | `GLOBAL_ENV` `BUILD_NUMBER`, then a `build_number` / `buildNumber` literal, then `client_build_number` |
| `version_hash` | `VERSION_HASH`, then a Sentry `buildId` tag, then a 40-character hex hash inside `SENTRY_RELEASE`, then the build-id header |
| `build_id` | `build_id_header`, then `version_hash` when the header is absent |
| `built_at` | `GLOBAL_ENV` `BUILT_AT`, stored as Discord sent it |
| `last_modified` | `last_modified_header`, stored as the raw HTTP date |
| `release_channel` | `RELEASE_CHANNEL`, cut at `release_channel_separator` (`-`) and lowercased, or the channel name when the page has none |
| `api_version` | `API_VERSION` |
| `gateway_endpoint` | `GATEWAY_ENDPOINT` |
| `api_endpoint` | `API_ENDPOINT` |
| `remote_auth_endpoint` | `REMOTE_AUTH_ENDPOINT` |
| `cdn_host` | `CDN_HOST` |
| `media_proxy_endpoint` | `MEDIA_PROXY_ENDPOINT` |
| `image_proxy_endpoints` | `IMAGE_PROXY_ENDPOINTS` |
| `rtc_latency_endpoint` | `RTC_LATENCY_ENDPOINT` |
| `networking_endpoint` | `NETWORKING_ENDPOINT` |
| `invite_host` | `INVITE_HOST` |
| `gift_code_host` | `GIFT_CODE_HOST` |
| `guild_template_host` | `GUILD_TEMPLATE_HOST` |
| `activity_application_host` | `ACTIVITY_APPLICATION_HOST` |
| `stripe_key` | `STRIPE_KEY` |
| `adyen_key` | `ADYEN_KEY` |
| `braintree_key` | `BRAINTREE_KEY` |
| `capabilities` | The largest `capabilities: N` literal, or the first branch of `flag ? A : B` |
| `capability_values` | Every distinct mask found beside `capabilities`, ascending |
| `client_build_number` | The first `client_build_number` assignment, including a nearby `parseInt` |
| `assets` | Content-hashed `/assets/{name}.{hash}.{ext}` links in the HTML, or in the scripts when the HTML has none |
| `gateway_encoding` | `json` and `etf` literals near an `encoding` field, first-seen order |
| `gateway_compress` | `zstd-stream` and `zlib-stream` literals, first-seen order |
| `scraped_at` | The run clock. See [Time](#time) |
| `channel` | The name you asked to scrape. It is the key in the snapshot, and a column on each history row |

Env keys are also accepted as camelCase and lower_snake. `""`, `undefined`,
`null`, and `none` are treated as missing (`empty_values`). A `GLOBAL_ENV`
object is read up to `max_env_chars` (200000) characters. Build hashes must be
7 to 64 hex digits. Asset hashes must be 8 to 40 hex digits. Asset extensions
are `js`, `css`, and `mjs`.

## Files

Paths below use the defaults: `data_dir = "data"`, stems `latest` and
`history`, `latest_formats` empty (so the snapshot follows `output_formats`),
and `output_formats = ["json"]`.

| File | When it is written | Contents |
| --- | --- | --- |
| `data/latest.json` | Every scrape, and a fetch when `write_on_fetch` is true | Current snapshot |
| `data/history.json` | Same runs. Also written when `json` is not an output format, because it is the append log | One object per observed build |
| `data/latest.md` | `md` is in `latest_formats`, or in `output_formats` when `latest_formats` is empty | Snapshot as Markdown tables |
| `data/latest.csv` | `csv` selected the same way | One row per channel. Nested values are JSON strings |
| `data/latest.toml` | `toml` selected the same way | Snapshot as TOML tables. Nulls are empty strings |
| `data/latest.yaml` | `yaml` selected the same way | Snapshot as YAML. Nulls are `null` |
| `data/history.md` | `md` is in `output_formats` | History as Markdown tables |
| `data/history.csv` | `csv` is in `output_formats` | One row per history object |
| `data/history.toml` | `toml` is in `output_formats` | History as `[[rows]]` tables |
| `data/history.yaml` | `yaml` is in `output_formats` | History as a YAML list |

`markdown` is an alias of `md`. `yml` is an alias of `yaml`.

`latest_dir` and `history_dir` replace `data_dir` for that file only.
`latest_filename` and `history_filename` replace the stems. The extension
comes from the format.

`write_output = false` skips files after a scrape. `--from-repo` does not
write files unless `write_on_fetch` is true.

JSON uses an indent of 2, insertion order, and a trailing newline. Indent `0`
is one compact line. `json_sort_keys = true` sorts keys. Those three options
apply only to JSON.

`drop_nulls = true` omits fields whose value is `None`. Empty lists are kept.
The default keeps nulls.

### Snapshot shape

```json
{
  "updated_at": "2026-11-25T14:00:00.123456+00:00",
  "channels": {
    "stable": {
      "build_number": 1,
      "version_hash": "...",
      "scraped_at": "2026-11-25T14:00:00.123456+00:00"
    }
  }
}
```

`latest_fields` chooses the keys inside each channel object, in that order.
The default is every surface field except `channel` (the channel is the object
key). Unknown names are rejected.

### History shape

`data/history.json` is a JSON array, the same role as
`discord_build_number_scrapper`'s `data/history.json`.

That other file stores `channel`, `build_number`, `build_hash`, `build_date`,
and `first_seen`. This file stores:

| Key | Meaning |
| --- | --- |
| `channel` | Channel name |
| `build_number` | Build number |
| `version_hash` | Build hash. This is the other project's `build_hash` |
| `build_id` | Build id from the hash or the response header |
| `capabilities` | Capability mask the page sends |
| `capability_values` | Every capability mask found beside that field |
| `client_build_number` | `client_build_number` from a script |
| `release_channel` | Channel name baked into the page |
| `built_at` | Build timestamp from `GLOBAL_ENV`. This is the other project's `build_date` |
| `first_seen` | When this row was first recorded |

A row is appended only when its key is new. The default key is `channel`,
`build_number`, `version_hash`, and `capabilities`. An empty `version_hash`
uses `build_id`. Numeric key fields are compared as integers. Everything else
is compared as text. Changing `history_key_fields` changes which later scrapes
count as the same build, including against rows already in the file.

`history_fields` chooses the keys written on a new row. The default is the
table above. The snapshot's `scraped_at` is not part of the default history
row. `first_seen` is.

The history log is always read from `{history_dir}/{history_filename}.json`
before new rows are merged, including when the history output format is not
JSON.

## Time

One clock instant is used for the whole run.

| Stored field | Format setting | Fallback |
| --- | --- | --- |
| `scraped_at` on each surface | `scraped_at_format` | `timestamp_format` |
| `updated_at` on the snapshot | `updated_at_format` | `timestamp_format` |
| `first_seen` on a new history row | `first_seen_format` | `timestamp_format` |

`timestamp_format = "iso"` calls `datetime.isoformat()`. Any other value is a
`strftime` pattern, for example `%Y-%m-%d`. An empty per-field format uses
`timestamp_format`.

`timezone` is `UTC`, `GMT`, `Z`, `local`, a numeric offset (`+03:00`,
`+0300`, `-05:00`), or an IANA name such as `Europe/Istanbul`.

`timestamp_microseconds` defaults to true. Set it false to zero the
microseconds before formatting. `isoformat()` then omits them.

`scraped_at` in the config, or `--scraped-at`, replaces "now". With
`timestamp_format = "iso"` the text is parsed by `datetime.fromisoformat`
(`Z` is accepted). Otherwise it is parsed with `timestamp_format`. A naive
value is given `timezone`.

`built_at` and `last_modified` are not passed through this clock. They are
copied from Discord.

## Read a published snapshot

```shell
uv run discry --from-repo
```

This fetches `latest_url` instead of scraping. The default URL is

```text
https://raw.githubusercontent.com/MFDI-hub/discry/main/data/latest.json
```

A GitHub blob URL (`https://github.com/.../blob/<ref>/data/latest.json`) is
turned into the matching raw URL. The fetch does not write files unless you
pass `--write-on-fetch` or set `write_on_fetch = true`.

```python
from discry import fetch_latest, fetch_latest_channel

latest = fetch_latest()
print(latest["stable"].build_number, latest["stable"].capabilities)
surface = fetch_latest_channel("ptb")
```

`fetch_latest()` uses `Settings().latest_url` when you omit the URL. Pass
`url=` or `settings=` to point it somewhere else.

## Call the scraper

```python
import asyncio
from datetime import datetime, timezone

from discry import scrape_channels
from discry.config import Settings, load_settings
from discry.history import write_data_files

settings = load_settings()
when = datetime.now(timezone.utc)
surfaces = asyncio.run(scrape_channels(settings=settings, scraped_at=when))
write_data_files(settings.data_dir, surfaces, scraped_at=when, settings=settings)
```

`load_settings()` applies `./config.toml` when that file exists, then
`SCRAPER_*`, then the `overrides` mapping. `environ=False` skips the
environment. `config_path=` selects a file. A missing explicit path raises
`FileNotFoundError`.

`scrape_channel()` scrapes one name. `SurfaceNotFoundError` means the page
could not be fetched or had no identity. `DiscryError` is the
base of that error and of `LatestFetchError`.

## GitHub

`.github/workflows/scrape.yml` runs at minute 23 of every hour, and when
someone starts it by hand.

The job checks out the repo, installs uv and Python 3.13, runs
`uv sync --locked --no-dev`, then `uv run discry` with:

| Variable | Source |
| --- | --- |
| `SCRAPER_PROXY` | Actions secret `SCRAPER_PROXY` |
| `SCRAPER_IMPERSONATE` | Actions variable `SCRAPER_IMPERSONATE` |
| `SCRAPER_LATEST_FORMATS` | `json,md,csv,toml,yaml` |

`output_formats` stays the default `json`, so the history log stays
`data/history.json`. The snapshot is committed as:

- `data/latest.json`
- `data/latest.md`
- `data/latest.csv`
- `data/latest.toml`
- `data/latest.yaml`

plus `data/history.json`. The job pushes branch `scrape/data` and merges a
pull request into `main`. `protect-main` rejects a direct push, and the
GitHub Actions app cannot be added to that ruleset on a personal account.
The commit message is `chore: update Discord client surface [skip ci]`. An
empty diff does not commit.

A failed scrape opens or comments on an issue labeled `scraper-failure`. A
later success closes those issues. Other job failures do not open that issue.

## Logging

The default level is `INFO` and the default format is
`%(levelname)s %(name)s: %(message)s`, written to stderr. `-v` / `--verbose`
forces `DEBUG` for that process and does not change the saved `log_level`.
`log_file` sends the log to that path instead of stderr.
