from __future__ import annotations

import uuid

from django.conf import settings
from django.http import HttpRequest, HttpResponse


class RequestIDMiddleware:
    """Attach a request correlation id and return it to the caller."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        incoming = request.headers.get("X-Request-ID", "").strip()
        request.request_id = incoming[:64] if incoming else uuid.uuid4().hex
        response = self.get_response(request)
        response["X-Request-ID"] = request.request_id
        return response


class SecurityHeadersMiddleware:
    """Headers that are not supplied consistently by Django's defaults."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response = self.get_response(request)

        exempt = any(
            request.path.startswith(prefix)
            for prefix in getattr(settings, "CSP_EXEMPT_PREFIXES", ())
        )
        if not exempt and getattr(settings, "CSP_POLICY", ""):
            response.setdefault("Content-Security-Policy", settings.CSP_POLICY)

        if getattr(settings, "PERMISSIONS_POLICY", ""):
            response.setdefault("Permissions-Policy", settings.PERMISSIONS_POLICY)

        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        response.setdefault("Referrer-Policy", "same-origin")
        return response
