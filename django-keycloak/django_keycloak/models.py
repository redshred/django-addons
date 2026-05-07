from django.conf import settings
from django.db import models
from django.utils import timezone


class OpenIdConnectProfile(models.Model):
    """Link between a Django ``User`` and a Keycloak account (by ``sub``)."""

    sub = models.CharField(max_length=255, unique=True)

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="oidc_profile",
        on_delete=models.CASCADE,
    )

    access_token = models.TextField(null=True)
    expires_before = models.DateTimeField(null=True)

    refresh_token = models.TextField(null=True)
    refresh_expires_before = models.DateTimeField(null=True)

    class Meta:
        swappable = "KEYCLOAK_OIDC_PROFILE_MODEL"

    @property
    def is_active(self) -> bool:
        if not self.access_token or not self.expires_before:
            return False
        return self.expires_before > timezone.now()
