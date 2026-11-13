from __future__ import annotations

from django.http import HttpRequest

from .permissions import primary_membership


def account_navigation(request: HttpRequest) -> dict:
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"nav_membership": None}
    return {"nav_membership": primary_membership(user)}
