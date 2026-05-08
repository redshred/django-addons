create # django-addons

A uv workspace housing reusable Django addons maintained by Redshred.

## Layout

Each addon lives in its own top-level directory with its own `pyproject.toml`
and is published to PyPI independently. The workspace root exists only to share
a single virtualenv, lockfile, and tooling config (ruff, dev deps).

## Members

| Directory | Package | Description |
| --- | --- | --- |
| [`django-request-id/`](django-request-id/) | `django-request-id` | Async-aware middleware that augments each request with a unique id for logging. |
| [`django-keycloak/`](django-keycloak/) | `django-keycloak` | Async-aware Keycloak/OIDC integration for Django. Hard fork of [skamansam/django-keycloak](https://github.com/skamansam/django-keycloak), being stripped down. |

### `django-request-id`

```python
# settings.py
MIDDLEWARE = [
    "request_id.middleware.RequestIdMiddleware",  # at the top
    # ... rest ...
]
INSTALLED_APPS = [..., "request_id"]  # only if you use the {% request_id %} tag
```

Add `request_id.logging.RequestIdFilter` to your `LOGGING` config and reference
`%(request_id)s` in a formatter to get the id in every log line. See
[`django-request-id/README.rst`](django-request-id/README.rst#quickstart) for
the full snippet.

### `django-keycloak`

```python
# settings.py
INSTALLED_APPS = [..., "django.contrib.sessions", "django.contrib.auth", "django_keycloak"]
AUTHENTICATION_BACKENDS = [
    "django_keycloak.auth.backends.KeycloakAuthorizationCodeBackend",
    "django_keycloak.auth.backends.KeycloakIDTokenAuthorizationBackend",
]
KEYCLOAK_SERVER_URL = "https://keycloak.example.com"
KEYCLOAK_REALM = "myrealm"
KEYCLOAK_CLIENT_ID = "myapp"
KEYCLOAK_CLIENT_SECRET = "..."
```

```python
# urls.py
urlpatterns = [path("auth/", include("django_keycloak.urls"))]
```

To accept a Keycloak access token as `Authorization: Bearer <token>` on API
endpoints, add `KeycloakStatelessBearerAuthenticationMiddleware` to
`MIDDLEWARE` and configure
`KEYCLOAK_BEARER_AUTHENTICATION_EXEMPT_PATHS`. See
[`django-keycloak/README.rst`](django-keycloak/README.rst#quickstart) for the
full setup.

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
