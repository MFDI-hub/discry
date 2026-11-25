## Install with pip

Python 3.8 or newer. `pip` installs `tomli` on 3.8–3.10. Python 3.11 and newer
use the standard-library `tomllib`.

```shell
pip install discry
discry
```

`python -m discry` is the same program.

From a checkout of this repo:

```shell
pip install -e .
discry
```

`-e` installs the checkout itself, so later edits are what the command runs.
The development tools in the next section need Python 3.11 or newer and are
installed with uv.

## Installing uv and Python

This project is set up to use [**uv**](https://docs.astral.sh/uv/) for Python and
dependency management.

### Install uv

On macOS or Linux:

```shell
curl -LsSf https://astral.sh/uv/install.sh | sh
```

On Windows (PowerShell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

If you use Homebrew (macOS):

```shell
brew update
brew install uv
```

See [uv's docs](https://docs.astral.sh/uv/getting-started/installation/) for all
supported installation methods.

### Install Python with uv

The installed package runs on Python 3.8 or newer. `curl-cffi` and `orjson`
pick an older release on 3.8 and 3.9 and a current release on 3.10 and newer.
Python 3.8 and 3.9 read `config.toml` with `tomli`. Python 3.11 and newer use
the standard-library `tomllib`.

IANA timezone names such as `Europe/Istanbul` need Python 3.9 or newer. On
3.8 use `UTC`, `local`, or a numeric offset such as `+03:00`.

Development tools (pytest 9, ruff, ty, mkdocs, pre-commit) need Python 3.11
or newer. Use 3.13 for a full checkout:

```shell
uv python install 3.13
```

### Install project dependencies

From your project root:

```shell
uv sync
```

This creates `.venv` and installs runtime + development dependencies.
