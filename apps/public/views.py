from __future__ import annotations

from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.services.views import get_featured_services


@require_GET
def home(request):
    return render(
        request,
        "public/home.html",
        {"featured_services": get_featured_services()},
    )


@require_GET
def privacy(request):
    return render(request, "public/privacy.html")


@require_GET
def not_found(request, exception=None):
    return render(request, "public/404.html", status=404)


@require_GET
def server_error(request):
    return render(request, "public/500.html", status=500)
