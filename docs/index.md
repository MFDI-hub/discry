# discry

Scrape the public Discord web client for the values that change with a build.

The package fetches `https://discord.com/app`, `https://ptb.discord.com/app`,
and `https://canary.discord.com/app` the same way
[discord_build_number_scrapper](https://github.com/MFDI-hub/discord_build_number_scrapper)
fetches a build number. No login. A field that disappears in a later build is
left empty. The rest of the snapshot is still written.

```shell
pip install discry
discry
```

```shell
uvx --from discry discry
```

```python
from discry import fetch_latest

latest = fetch_latest()
print(latest["stable"].build_number, latest["stable"].capabilities)
```

## What gets saved

A normal local run writes two files:

- `data/latest.json` is the current snapshot of every channel. `updated_at`
  is the run clock. Each channel object holds the surface fields, including
  `scraped_at`.
- `data/history.json` is an append-only log, the same role as
  `discord_build_number_scrapper`'s `data/history.json`. A row is added when
  `channel`, `build_number`, `version_hash`, or `capabilities` changes. An
  empty version hash falls back to `build_id`. At 95 MB the file is renamed
  with the UTC time it closed, and a new `data/history.json` continues the log.
  The app page and its scripts are saved under `data/client/<channel>/` and
  replaced when the code changes.

The snapshot can also be written as Markdown, CSV, TOML, and YAML. History
can use those formats too. The hourly GitHub workflow writes all five snapshot
formats and keeps history as JSON.

The other project's history columns are `channel`, `build_number`,
`build_hash`, `build_date`, and `first_seen`. This project's default history
columns are `channel`, `build_number`, `version_hash`, `build_id`,
`capabilities`, `capability_values`, `client_build_number`,
`release_channel`, `built_at`, and `first_seen`.

## Pages

- [Installation](installation.md) covers Python 3.10+ for the package and 3.11+ for development.
- [Usage](usage.md) covers a scrape, the files, the clock, `--from-repo`, and GitHub.
- [Configuration](configuration.md) lists every setting, its default, its environment variable, and the CLI flags.
- [API reference](reference/discry/index.md) is generated from the docstrings, one page per module.
