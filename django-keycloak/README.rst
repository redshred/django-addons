===============
django-keycloak
===============

Async-aware Django integration for Keycloak.

This is a hard fork of `skamansam/django-keycloak`_ (itself a fork of
`Peter-Slump/django-keycloak`_), maintained by Redshred and stripped down to
the OAuth2 / OIDC features we use:

- Authorization-code login that pairs a Django ``User`` with a Keycloak
  account (linked by ``sub``).
- A bearer-token authentication backend so a Keycloak access token can be
  used in place of an application-specific token.

UMA, fine-grained permissions, federation, the remote-user model, and the
upstream example apps have been removed.


Quickstart
==========

Install
-------

.. code-block:: bash

   pip install django-keycloak

(Or add it as a workspace dependency if you're using uv.)

Settings
--------

Required:

.. code-block:: python

   INSTALLED_APPS = [
       # ...
       "django.contrib.sessions",
       "django.contrib.auth",
       "django_keycloak",
   ]

   AUTHENTICATION_BACKENDS = [
       # Browser login (OAuth2 authorization code):
       "django_keycloak.auth.backends.KeycloakAuthorizationCodeBackend",
       # API auth via Keycloak access token in Authorization: Bearer:
       "django_keycloak.auth.backends.KeycloakIDTokenAuthorizationBackend",
   ]

   KEYCLOAK_SERVER_URL = "https://keycloak.example.com"
   KEYCLOAK_REALM = "myrealm"
   KEYCLOAK_CLIENT_ID = "myapp"
   KEYCLOAK_CLIENT_SECRET = "..."   # secret from the Keycloak client

Optional:

.. code-block:: python

   # When server-to-server traffic goes through a different host than the
   # public URL (Docker Compose, internal DNS):
   KEYCLOAK_SERVER_INTERNAL_URL = "http://keycloak:8080"

   # JWKS / .well-known cache lifetime in seconds (default 3600):
   KEYCLOAK_CACHE_TIMEOUT = 3600

URLs
----

Mount the login / callback / logout views wherever you like:

.. code-block:: python

   # urls.py
   from django.urls import include, path

   urlpatterns = [
       path("auth/", include("django_keycloak.urls")),
   ]

This exposes ``auth/login``, ``auth/login-complete``, and ``auth/logout``
(named ``keycloak_login``, ``keycloak_login_complete``, ``keycloak_logout``).
The ``redirect_uri`` registered on the Keycloak client must match
``<your-host>/auth/login-complete``.

API auth via bearer token (optional)
------------------------------------

To accept a Keycloak access token as ``Authorization: Bearer <token>`` on
your API endpoints, add the bearer middleware. It's compatible with both
WSGI and ASGI deployments:

.. code-block:: python

   MIDDLEWARE = [
       # ... session + auth middleware first ...
       "django_keycloak.middleware.KeycloakStatelessBearerAuthenticationMiddleware",
   ]

   # Paths that should bypass bearer auth (regex, matched against the
   # leading-slash-stripped path):
   KEYCLOAK_BEARER_AUTHENTICATION_EXEMPT_PATHS = [
       r"^auth/.*",          # the OIDC login endpoints themselves
       r"^healthz$",
   ]

Run migrations
--------------

.. code-block:: bash

   python manage.py migrate django_keycloak

Status
======

Pre-alpha. APIs and the data model are unstable while the strip-down and
async conversion are in progress.

License
=======

MIT, retained from upstream. See ``LICENSE``.

.. _skamansam/django-keycloak: https://github.com/skamansam/django-keycloak
.. _Peter-Slump/django-keycloak: https://github.com/Peter-Slump/django-keycloak
