from django.http.response import HttpResponse


class HttpResponseNotAuthorized(HttpResponse):
    status_code = 401

    def __init__(self, content=b"", authorization_method="Bearer", attributes=None, *args, **kwargs):
        super().__init__(content, *args, **kwargs)

        attributes = attributes or {}
        attributes_str = ", ".join([f'{key}="{value}"' for key, value in attributes.items()])

        self["WWW-Authenticate"] = f"{authorization_method} {attributes_str}"
