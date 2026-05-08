from django.conf import settings
from django.db import models
from django.utils import timezone

# Tokens use null=True (DJ001) deliberately: NULL is the "no token, logged
# out" sentinel and is semantically distinct from an empty string. Using
# blank="" would conflate the two states.


class OpenIdConnectProfile(models.Model):
    """Link between a Django ``User`` and a Keycloak account (by ``sub``)."""

    sub = models.CharField(max_length=255, unique=True)

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        related_name="oidc_profile",
        on_delete=models.CASCADE,
    )

    access_token = models.TextField(null=True)  # noqa: DJ001
    expires_before = models.DateTimeField(null=True)

    refresh_token = models.TextField(null=True)  # noqa: DJ001
    refresh_expires_before = models.DateTimeField(null=True)

    # Stored at login so RP-initiated logout can pass it as ``id_token_hint``
    # to Keycloak's end_session_endpoint. Refresh-token grants do not return
    # a new id_token, so this column is only refreshed on initial login.
    id_token = models.TextField(null=True)  # noqa: DJ001

    class Meta:
        swappable = "KEYCLOAK_OIDC_PROFILE_MODEL"

    def __str__(self) -> str:
        return f"{self.user} ({self.sub})"

    @property
    def is_active(self) -> bool:
        if not self.access_token or not self.expires_before:
            return False
        return self.expires_before > timezone.now()
