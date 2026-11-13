from __future__ import annotations

import re

from django.conf import settings
from django.http import HttpRequest
from django.utils.translation import get_language


def site_context(request: HttpRequest) -> dict:
    return {
        "DEMO_MODE": settings.DEMO_MODE,
        "SITE_NAME": settings.SITE_NAME,
        "SITE_TAGLINE": settings.SITE_TAGLINE,
    }


def language_switch(request: HttpRequest) -> dict:
    current = get_language() or settings.LANGUAGE_CODE
    other = "fr" if current.startswith("en") else "en"

    match = re.match(r"^/(en|fr)(/.*)?$", request.path)
    if match:
        new_path = f"/{other}{match.group(2) or '/'}"
    else:
        new_path = f"/{other}{request.path}"

    query = request.META.get("QUERY_STRING", "")
    if query:
        new_path = f"{new_path}?{query}"

    return {
        "current_language": current,
        "language_switch_url": new_path,
        "language_switch_label": "Français" if current.startswith("en") else "English",
    }
