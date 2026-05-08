"""Verify Keycloak settings + connectivity by hitting well-known + JWKS."""

import asyncio

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from django_keycloak import conf


class Command(BaseCommand):
    help = (
        "Smoke-check the Keycloak configuration: validate required settings, "
        "fetch .well-known/openid-configuration, and fetch JWKS. Bypasses the "
        "cache so it actually reaches Keycloak."
    )

    def handle(self, *args, **options):
        required = (
            "KEYCLOAK_SERVER_URL",
            "KEYCLOAK_REALM",
            "KEYCLOAK_CLIENT_ID",
            "KEYCLOAK_CLIENT_SECRET",
        )
        missing = [name for name in required if not getattr(settings, name, None)]
        if missing:
            raise CommandError(f"Missing required settings: {', '.join(missing)}")

        self.stdout.write(f"Public URL:   {settings.KEYCLOAK_SERVER_URL}")
        internal = getattr(settings, "KEYCLOAK_SERVER_INTERNAL_URL", None)
        if internal:
            self.stdout.write(f"Internal URL: {internal}")
        self.stdout.write(f"Realm:        {settings.KEYCLOAK_REALM}")
        self.stdout.write(f"Client ID:    {settings.KEYCLOAK_CLIENT_ID}")
        self.stdout.write("")

        try:
            asyncio.run(self._probe())
        except Exception as exc:
            raise CommandError(f"Keycloak probe failed: {exc}") from exc

        self.stdout.write(self.style.SUCCESS("OK — Keycloak is reachable."))

    async def _probe(self):
        # Bypass cache so we actually round-trip Keycloak.
        await conf.refresh_cache()

        well_known = await conf.get_well_known_oidc()
        self.stdout.write(f"issuer:                {well_known['issuer']}")
        self.stdout.write(f"authorization_endpoint: {well_known['authorization_endpoint']}")
        self.stdout.write(f"token_endpoint:        {well_known['token_endpoint']}")
        self.stdout.write(f"jwks_uri:              {well_known['jwks_uri']}")
        end_session = well_known.get("end_session_endpoint")
        if end_session:
            self.stdout.write(f"end_session_endpoint:  {end_session}")
        else:
            self.stdout.write(
                self.style.WARNING(
                    "end_session_endpoint missing — RP-initiated logout will fall back to local-only logout."
                )
            )

        certs = await conf.get_certs()
        self.stdout.write(f"JWKS keys:             {len(certs.get('keys', []))}")
