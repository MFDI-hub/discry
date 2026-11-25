# discord_client_scrapper

[![CI](https://github.com/MFDI-hub/discord_client_scrapper/actions/workflows/ci.yml/badge.svg)](https://github.com/MFDI-hub/discord_client_scrapper/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/discord_client_scrapper)](https://pypi.org/project/discord_client_scrapper/)
[![Python versions](https://img.shields.io/pypi/pyversions/discord_client_scrapper)](https://pypi.org/project/discord_client_scrapper/)

> **This is the initial readme for your project from the
> [python-template](https://github.com/MFDI-hub/python-template) Copier template.** Fill it in and
> delete this message!
> Below are general setup instructions that you may remove or keep and adapt for your
> project.

* * *

## Project Docs

For how to install uv and Python, see [installation.md](docs/installation.md).

For development workflows, see [development.md](docs/development.md).

For instructions on publishing to PyPI, see [publishing.md](docs/publishing.md).

## Quickstart

```shell
# Install project dependencies + git hooks (commit, commit-msg, pre-push):
make install
# or: uv sync && uv run pre-commit install && uv run pre-commit install --hook-type commit-msg && uv run pre-commit install --hook-type pre-push

# Run quality checks:
uv run python devtools/lint.py
uv run pytest -n auto --cov --cov-report=term-missing

# Build package artifacts:
uv build --no-sources
```

## Lockfile (`uv.lock`)

Commit `uv.lock`. CI runs `uv sync --locked` and fails when the lockfile is missing
or stale. The lockfile pins this repository's development environment. Published
installs resolve from the version ranges in `pyproject.toml`.

* * *

*This project was built from
[python-template](https://github.com/MFDI-hub/python-template).*
