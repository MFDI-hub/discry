# Configuration

Settings are loaded in this order. A later layer replaces the same field from
an earlier layer:

1. Built-in defaults.
2. `config.toml` in the working directory, or the file named by `--config` or
   `SCRAPER_CONFIG`.
3. `SCRAPER_*` environment variables that are set and non-empty.
4. CLI flags, then `--set key=value` is applied first so a dedicated flag wins.

`load_settings()` validates the result. An unknown key, an empty channel list,
a channel with no domain, a bad number, or an unknown format raises
`ValueError` and the CLI exits `1`.

The checked-in `config.toml` shows the values people change most often. Every
other default is commented there.

## Types

| Kind | TOML | Environment and `--set` |
| --- | --- | --- |
| string | `"chrome"` | text |
| optional string | omit the key, or `""` | omit the variable. `""`, `0`, `false`, `none`, and `off` clear it |
| bool | `true` / `false` | `1`, `true`, `yes`, `on` / `0`, `false`, `no`, `off` |
| optional bool | omit the key for "leave the library alone" | same words. Empty unsets it |
| number | `30` or `0.5` | the same text |
| list | `["stable", "ptb"]` | comma-separated. Blank pieces are dropped, except inside `empty_values` |
| table | `[headers]` then `Name = "value"` | a JSON object |

`http2` is the optional bool. `connect_timeout` is the optional number. Empty
means unset. `0` is not a way to clear `connect_timeout`.

List aliases: `markdown` becomes `md`, `yml` becomes `yaml`. `log_level` is
uppercased. `url_scheme`, `identity_match`, `release_channel_case`,
`asset_extensions`, `script_extensions`, and `empty_values` are lowercased.
Header names are lowercased. `app_path` and `asset_prefix` gain a leading `/`
when missing, and `asset_prefix` gains a trailing `/`. `asset_base_url` loses
trailing slashes.

Environment names are `SCRAPER_` plus the field name in upper case.
`download_concurrency` is the exception: `SCRAPER_CONCURRENCY`.
`SCRAPER_CONFIG` is the config file path, not a `Settings` field.

## CLI flags

| Flag | Setting |
| --- | --- |
| `--config PATH` | config file. Default: `./config.toml` when that file exists |
| `--set KEY=VALUE` | any field. Repeatable. Lists are comma-separated. Tables are JSON |
| `--impersonate PROFILE` | `impersonate` |
| `--proxy URL` | `proxy` |
| `--timeout SECONDS` | `timeout` |
| `--no-verify` | `verify = false` |
| `--channel NAME` | `channels`. Repeatable. Replaces the whole list |
| `--data-dir PATH` | `data_dir` |
| `--max-files N` | `max_files` |
| `--concurrency N` | `download_concurrency` |
| `--asset-base-url URL` | `asset_base_url` |
| `--from-repo` | `from_repo = true` |
| `--latest-url URL` | `latest_url` |
| `--output-format NAME` | `output_formats`. Repeatable. Choices: `json`, `md`, `markdown`, `csv`, `toml`, `yaml`, `yml` |
| `--timezone NAME` | `timezone` |
| `--timestamp-format PATTERN` | `timestamp_format` |
| `--scraped-at TEXT` | `scraped_at` |
| `--log-level LEVEL` | `log_level` |
| `--log-file PATH` | `log_file` |
| `--write-on-fetch` | `write_on_fetch = true` |
| `-v`, `--verbose` | forces log level `DEBUG` for this process only |

There is no flag that turns `from_repo` or `write_on_fetch` back off. Use
`--set from_repo=false` or `--set write_on_fetch=false`.

## Output

| Field | Default | Env | Meaning |
| --- | --- | --- | --- |
| `output_formats` | `json` | `SCRAPER_OUTPUT_FORMATS` | Formats for the history log. Also used for the snapshot when `latest_formats` is empty |
| `latest_formats` | empty | `SCRAPER_LATEST_FORMATS` | Formats for the snapshot. Empty means `output_formats` |
| `json_indent` | `2` | `SCRAPER_JSON_INDENT` | Spaces per JSON level. `0` writes one line |
| `json_sort_keys` | `false` | `SCRAPER_JSON_SORT_KEYS` | Sort JSON object keys |
| `json_trailing_newline` | `true` | `SCRAPER_JSON_TRAILING_NEWLINE` | End JSON files with a newline |
| `latest_filename` | `latest` | `SCRAPER_LATEST_FILENAME` | Snapshot file stem. The extension comes from the format |
| `history_filename` | `history` | `SCRAPER_HISTORY_FILENAME` | History file stem |
| `latest_dir` | unset | `SCRAPER_LATEST_DIR` | Snapshot directory. Unset uses `data_dir` |
| `history_dir` | unset | `SCRAPER_HISTORY_DIR` | History directory. Unset uses `data_dir` |
| `data_dir` | `data` | `SCRAPER_DATA_DIR` | Directory used when a specific directory is unset |
| `write_output` | `true` | `SCRAPER_WRITE_OUTPUT` | Write files after a scrape |
| `write_on_fetch` | `false` | `SCRAPER_WRITE_ON_FETCH` | Write files after `--from-repo` |
| `drop_nulls` | `false` | `SCRAPER_DROP_NULLS` | Omit fields whose value is `None` |
| `latest_fields` | every surface field except `channel` | `SCRAPER_LATEST_FIELDS` | Keys stored inside each channel of the snapshot, in this order |
| `history_fields` | see below | `SCRAPER_HISTORY_FIELDS` | Keys stored on a history row, in this order |
| `history_key_fields` | `channel`, `build_number`, `version_hash`, `capabilities` | `SCRAPER_HISTORY_KEY_FIELDS` | Fields that decide whether a row is new |

Allowed format names are `json`, `md`, `csv`, `toml`, and `yaml`. At least one
`output_formats` entry is required. `latest_formats` may be empty.

Default `history_fields`:

`channel`, `build_number`, `version_hash`, `build_id`, `capabilities`,
`capability_values`, `client_build_number`, `release_channel`, `built_at`,
`first_seen`.

Default `latest_fields`:

`build_number`, `version_hash`, `build_id`, `built_at`, `last_modified`,
`release_channel`, `api_version`, `gateway_endpoint`, `api_endpoint`,
`remote_auth_endpoint`, `cdn_host`, `media_proxy_endpoint`,
`image_proxy_endpoints`, `rtc_latency_endpoint`, `networking_endpoint`,
`invite_host`, `gift_code_host`, `guild_template_host`,
`activity_application_host`, `assets`, `gateway_encoding`,
`gateway_compress`, `stripe_key`, `adyen_key`, `braintree_key`,
`capabilities`, `capability_values`, `client_build_number`, `scraped_at`.

`channel` may be added to `latest_fields`. `first_seen` may be added to
`history_fields` and is already in the default. Any other name is rejected.

On a history key, an empty `version_hash` falls back to `build_id`.
`build_number`, `capabilities`, `client_build_number`, and `api_version` are
compared as integers. Other key fields are compared as text.

The hourly workflow sets `SCRAPER_LATEST_FORMATS=json,md,csv,toml,yaml` and
leaves `output_formats` at `json`.

## Time

| Field | Default | Env | Meaning |
| --- | --- | --- | --- |
| `timezone` | `UTC` | `SCRAPER_TIMEZONE` | `UTC`, `GMT`, `Z`, `local`, `+HH:MM`, `+HHMM`, `-HH:MM`, or an IANA name |
| `timestamp_format` | `iso` | `SCRAPER_TIMESTAMP_FORMAT` | `iso`, or a `strftime` pattern |
| `timestamp_microseconds` | `true` | `SCRAPER_TIMESTAMP_MICROSECONDS` | Keep microseconds. `false` zeros them before formatting |
| `scraped_at` | unset | `SCRAPER_SCRAPED_AT` | Use this instant instead of now |
| `scraped_at_format` | empty | `SCRAPER_SCRAPED_AT_FORMAT` | Format for the surface `scraped_at`. Empty uses `timestamp_format` |
| `updated_at_format` | empty | `SCRAPER_UPDATED_AT_FORMAT` | Format for the snapshot `updated_at` |
| `first_seen_format` | empty | `SCRAPER_FIRST_SEEN_FORMAT` | Format for history `first_seen` |

IANA names such as `Europe/Istanbul` are accepted. A bad pattern or an
unparsable `scraped_at` fails validation. See [Usage](usage.md#time) for which
field uses which format. `built_at` and `last_modified` are not reformatted.

## Fetch

| Field | Default | Env | Meaning |
| --- | --- | --- | --- |
| `impersonate` | `chrome` | `SCRAPER_IMPERSONATE` | curl_cffi browser profile. Must be one the installed curl_cffi knows, and must not be blank |
| `proxy` | unset | `SCRAPER_PROXY` | Used for both HTTP and HTTPS when the split proxies are unset |
| `http_proxy` | unset | `SCRAPER_HTTP_PROXY` | HTTP proxy. Overrides `proxy` for HTTP |
| `https_proxy` | unset | `SCRAPER_HTTPS_PROXY` | HTTPS proxy. Overrides `proxy` for HTTPS |
| `no_proxy` | unset | `SCRAPER_NO_PROXY` | Comma-separated hosts that skip the proxy. `*` skips every host. A name also matches subdomains |
| `timeout` | `30` | `SCRAPER_TIMEOUT` | Read timeout in seconds. Must be greater than 0. Also the whole-request timeout when `connect_timeout` is unset |
| `connect_timeout` | unset | `SCRAPER_CONNECT_TIMEOUT` | Connect timeout in seconds. The request timeout becomes `(connect_timeout, timeout)` |
| `verify` | `true` | `SCRAPER_VERIFY` | Verify TLS certificates |
| `retries` | `0` | `SCRAPER_RETRIES` | Extra attempts after the first. `0` means one try. HTTP errors and connection errors are both retried |
| `retry_backoff` | `0` | `SCRAPER_RETRY_BACKOFF` | Seconds times the attempt number, slept between retries |
| `max_redirects` | `30` | `SCRAPER_MAX_REDIRECTS` | Redirect limit. `-1` means no limit. Must be at least `-1` |
| `headers` | `{}` | `SCRAPER_HEADERS` | Extra request headers. A header passed by the caller overrides the same name |
| `cookies` | `{}` | `SCRAPER_COOKIES` | Cookies sent on each request |
| `http2` | unset | `SCRAPER_HTTP2` | `true` forces HTTP/2, `false` forces HTTP/1.1. Unset leaves curl_cffi's default |
| `curl_options` | `{}` | `SCRAPER_CURL_OPTIONS` | Extra keyword arguments passed to curl_cffi. Applied last, so they override the fields above |
| `channels` | `stable`, `ptb`, `canary` | `SCRAPER_CHANNELS` | Channels to scrape, in order. Must not be empty |
| `domains` | the three hosts below | `SCRAPER_DOMAINS` | Channel name to hostname |
| `domains_replace` | `false` | `SCRAPER_DOMAINS_REPLACE` | `true` replaces the built-in map. `false` merges on top of it |
| `url_scheme` | `https` | `SCRAPER_URL_SCHEME` | `https` or `http` |
| `app_path` | `/app` | `SCRAPER_APP_PATH` | Path fetched on each channel host |
| `asset_prefix` | `/assets/` | `SCRAPER_ASSET_PREFIX` | Path prefix searched for scripts and content-hashed files |
| `asset_base_url` | unset | `SCRAPER_ASSET_BASE_URL` | Origin for downloaded asset paths. Unset uses `{url_scheme}://{host}` |
| `channel_concurrency` | `1` | `SCRAPER_CHANNEL_CONCURRENCY` | How many channels are fetched at once. Results stay in request order |
| `continue_on_error` | `false` | `SCRAPER_CONTINUE_ON_ERROR` | Return the channels that succeeded. An empty success list still fails |
| `from_repo` | `false` | `SCRAPER_FROM_REPO` | Fetch `latest_url` instead of scraping |
| `latest_url` | the raw `data/latest.json` on `main` | `SCRAPER_LATEST_URL` | Snapshot URL. GitHub blob URLs are converted to raw |

Built-in domains:

| Channel | Host |
| --- | --- |
| `stable` | `discord.com` |
| `ptb` | `ptb.discord.com` |
| `canary` | `canary.discord.com` |

To scrape only a custom channel, set `domains_replace = true` and list every
host you still want. A merge keeps the three built-in rows.

```toml
channels = ["staging"]
domains_replace = true

[domains]
staging = "staging.discord.com"
```

`impersonate` is checked against curl_cffi's `BrowserTypeLiteral` when that
list can be imported. `chrome` is the usual alias.

## Scrape stop and scripts

| Field | Default | Env | Meaning |
| --- | --- | --- | --- |
| `max_files` | `40` | `SCRAPER_MAX_FILES` | Maximum script bodies inspected per channel. At least 1 |
| `download_concurrency` | `8` | `SCRAPER_CONCURRENCY` | Parallel script downloads inside one channel. At least 1 |
| `script_priority` | `fast-connect.`, `web.`, `sentry.` | `SCRAPER_SCRIPT_PRIORITY` | Filename prefixes fetched first, in this order |
| `script_extensions` | `js` | `SCRAPER_SCRIPT_EXTENSIONS` | Extensions collected from script and stylesheet tags. Must not be empty |
| `identity_fields` | `build_number`, `version_hash`, `build_id` | `SCRAPER_IDENTITY_FIELDS` | Fields that make a channel successful |
| `identity_match` | `any` | `SCRAPER_IDENTITY_MATCH` | `any` or `all` |
| `skip_script_fields` | `capabilities`, `client_build_number` | `SCRAPER_SKIP_SCRIPT_FIELDS` | All of these, plus the identity match, must be set to skip script downloads |
| `rest_script_fields` | `capabilities`, `build_number` | `SCRAPER_REST_SCRIPT_FIELDS` | If any of these is missing, non-priority scripts are downloaded too |
| `stop_fields` | `build_number`, `capabilities` | `SCRAPER_STOP_FIELDS` | All of these must be set before downloads can stop |
| `stop_early_fields` | `client_build_number` | `SCRAPER_STOP_EARLY_FIELDS` | All of these let the download stop before the priority scripts are finished. After the priority scripts, `stop_fields` alone is enough |

An empty `stop_early_fields` list means "no extra requirement": downloads stop
as soon as `stop_fields` are all set.

A field counts as present when it is not `None`. Empty lists, tuples, and
dicts count as absent. `0` counts as present.

Field names in these lists must be surface attributes: `channel`,
`build_number`, `version_hash`, `build_id`, `built_at`, `last_modified`,
`release_channel`, `api_version`, `gateway_endpoint`, `api_endpoint`,
`remote_auth_endpoint`, `cdn_host`, `media_proxy_endpoint`,
`image_proxy_endpoints`, `rtc_latency_endpoint`, `networking_endpoint`,
`invite_host`, `gift_code_host`, `guild_template_host`,
`activity_application_host`, `assets`, `gateway_encoding`,
`gateway_compress`, `stripe_key`, `adyen_key`, `braintree_key`,
`capabilities`, `capability_values`, `client_build_number`, `scraped_at`.

## Parsing

| Field | Default | Env | Meaning |
| --- | --- | --- | --- |
| `max_env_chars` | `200000` | `SCRAPER_MAX_ENV_CHARS` | Maximum characters read from one `GLOBAL_ENV` object |
| `hash_min_length` | `7` | `SCRAPER_HASH_MIN_LENGTH` | Shortest accepted build hash |
| `hash_max_length` | `64` | `SCRAPER_HASH_MAX_LENGTH` | Longest accepted build hash |
| `asset_hash_min_length` | `8` | `SCRAPER_ASSET_HASH_MIN_LENGTH` | Shortest accepted asset hash |
| `asset_hash_max_length` | `40` | `SCRAPER_ASSET_HASH_MAX_LENGTH` | Longest accepted asset hash |
| `capability_literal_min_digits` | `3` | `SCRAPER_CAPABILITY_LITERAL_MIN_DIGITS` | Shortest `capabilities: N` number |
| `capability_literal_max_digits` | `10` | `SCRAPER_CAPABILITY_LITERAL_MAX_DIGITS` | Longest `capabilities: N` number |
| `capability_ternary_min_digits` | `4` | `SCRAPER_CAPABILITY_TERNARY_MIN_DIGITS` | Shortest number in `flag ? A : B` |
| `capability_ternary_max_digits` | `10` | `SCRAPER_CAPABILITY_TERNARY_MAX_DIGITS` | Longest number in that ternary |
| `build_number_min_digits` | `4` | `SCRAPER_BUILD_NUMBER_MIN_DIGITS` | Shortest accepted build number and `client_build_number` |
| `release_channel_separator` | `-` | `SCRAPER_RELEASE_CHANNEL_SEPARATOR` | Cut `RELEASE_CHANNEL` at the first occurrence. Empty keeps the whole value |
| `release_channel_case` | `lower` | `SCRAPER_RELEASE_CHANNEL_CASE` | `lower`, `upper`, or `preserve` |
| `empty_values` | `""`, `undefined`, `null`, `none` | `SCRAPER_EMPTY_VALUES` | Strings treated as missing. Compared after strip and lowercasing |
| `env_markers` | `window.GLOBAL_ENV`, `GLOBAL_ENV` | `SCRAPER_ENV_MARKERS` | Text that introduces a `GLOBAL_ENV` object, searched in this order |
| `build_id_header` | `x-build-id` | `SCRAPER_BUILD_ID_HEADER` | Response header read as the build id |
| `last_modified_header` | `last-modified` | `SCRAPER_LAST_MODIFIED_HEADER` | Response header stored as `last_modified` |
| `asset_extensions` | `js`, `css`, `mjs` | `SCRAPER_ASSET_EXTENSIONS` | Content-hashed extensions to keep. Each one must be one of those three |

Each minimum length must be at least 1 and must not exceed its maximum.
Gateway encoding names (`json`, `etf`) and compression names
(`zstd-stream`, `zlib-stream`) are fixed.

## Logging and the snapshot URL

| Field | Default | Env | Meaning |
| --- | --- | --- | --- |
| `log_level` | `INFO` | `SCRAPER_LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` |
| `log_format` | `%(levelname)s %(name)s: %(message)s` | `SCRAPER_LOG_FORMAT` | `logging` format string |
| `log_file` | unset | `SCRAPER_LOG_FILE` | Log file. Unset logs to stderr |
| `latest_url` | `https://raw.githubusercontent.com/MFDI-hub/discry/main/data/latest.json` | `SCRAPER_LATEST_URL` | URL used by `--from-repo` and `fetch_latest()` |
| `from_repo` | `false` | `SCRAPER_FROM_REPO` | Read that URL instead of scraping |

## Examples

Snapshot in every format, history still JSON, clocks in `+03:00` without
microseconds:

```toml
latest_formats = ["json", "md", "csv", "toml", "yaml"]
timezone = "+03:00"
timestamp_microseconds = false
```

The same snapshot choice from the environment:

```shell
SCRAPER_LATEST_FORMATS=json,md,csv,toml,yaml uv run discry
```

One channel, a proxy, and a pinned timestamp:

```shell
uv run discry \
  --channel stable \
  --proxy socks5://127.0.0.1:1080 \
  --scraped-at 2026-11-25T12:00:00+00:00
```

A header table and a curl_cffi extra from `--set`:

```shell
uv run discry \
  --set 'headers={"Accept-Language":"en-US,en;q=0.9"}' \
  --set 'curl_options={"interface":"127.0.0.1"}'
```
