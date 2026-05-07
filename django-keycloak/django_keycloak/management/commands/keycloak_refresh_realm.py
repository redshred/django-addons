"""Refresh the cached well-known + JWKS documents from Keycloak."""

import asyncio
import logging

from django.core.management.base import BaseCommand

from django_keycloak import conf

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Refresh cached Keycloak .well-known and JWKS documents."

    def handle(self, *args, **options):
        asyncio.run(conf.refresh_cache())
        self.stdout.write(self.style.SUCCESS("Keycloak cache refreshed"))
