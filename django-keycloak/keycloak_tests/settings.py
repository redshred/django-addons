SECRET_KEY = "test-secret-key"
DEBUG = True
USE_TZ = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django_keycloak",
]

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]

AUTHENTICATION_BACKENDS = [
    "django_keycloak.auth.backends.KeycloakAuthorizationCodeBackend",
    "django_keycloak.auth.backends.KeycloakIDTokenAuthorizationBackend",
]

CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
}

SESSION_ENGINE = "django.contrib.sessions.backends.cache"

ROOT_URLCONF = "keycloak_tests.urls"

LOGIN_REDIRECT_URL = None
LOGOUT_REDIRECT_URL = None

KEYCLOAK_SERVER_URL = "https://kc.example.com"
KEYCLOAK_REALM = "testrealm"
KEYCLOAK_CLIENT_ID = "testclient"
KEYCLOAK_CLIENT_SECRET = "testsecret"
KEYCLOAK_CACHE_TIMEOUT = 3600
