# django-addons

A uv workspace housing reusable Django addons maintained by Redshred.

## Layout

Each addon lives in its own top-level directory with its own `pyproject.toml`
and is published to PyPI independently. The workspace root exists only to share
a single virtualenv, lockfile, and tooling config (ruff, dev deps).

## Members

| Directory | Package | Description |
| --- | --- | --- |
| [`django-request-id/`](django-request-id/) | `django-request-id` | Async-aware middleware that augments each request with a unique id for logging. |

## Working in the workspace

```bash
uv sync                       # install all members + dev deps into .venv
uv run --directory django-request-id pytest    # run tests for one addon
uv run ruff check             # lint everything
```

## Adding a new addon

1. Create a new top-level directory `<addon>/` with its own `pyproject.toml`.
2. Add it to `members` in the root `pyproject.toml`.
3. Run `uv sync`.
