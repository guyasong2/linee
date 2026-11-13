from __future__ import annotations

from typing import Any

from django.http import HttpRequest

from .models import AuditLog

SENSITIVE_KEYS = {
    "password",
    "password1",
    "password2",
    "otp",
    "pin",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "authorization",
    "card_number",
    "cvv",
}


def redact(value: Any) -> Any:
    """Return audit-safe data without credentials, OTPs or payment secrets."""
    if isinstance(value, dict):
        return {
            str(key): "***" if str(key).lower() in SENSITIVE_KEYS else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str) and len(value) > 2000:
        return value[:2000] + "…"
    return value


def _client_ip(request: HttpRequest) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()[:64]
    return request.META.get("REMOTE_ADDR")


def record_audit(
    *,
    action: str,
    resource_type: str,
    organization=None,
    actor=None,
    resource_public_id: str = "",
    before: Any = None,
    after: Any = None,
    reason: str = "",
    request: HttpRequest | None = None,
    request_id: str = "",
    ip_address: str | None = None,
    user_agent: str = "",
) -> AuditLog:
    if request is not None:
        request_id = request_id or getattr(request, "request_id", "")
        if actor is None:
            candidate = getattr(request, "user", None)
            if candidate is not None and getattr(candidate, "is_authenticated", False):
                actor = candidate
        ip_address = ip_address or _client_ip(request)
        user_agent = user_agent or request.META.get("HTTP_USER_AGENT", "")

    return AuditLog.objects.create(
        organization=organization,
        actor=actor,
        action=action[:80],
        resource_type=resource_type[:80],
        resource_public_id=str(resource_public_id)[:64],
        before=redact(before or {}),
        after=redact(after or {}),
        reason=reason[:240],
        request_id=request_id[:64],
        ip_address=ip_address,
        user_agent=user_agent[:300],
    )
