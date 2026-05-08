from django.urls import include, path

urlpatterns = [
    path("kc/", include("django_keycloak.urls")),
]
