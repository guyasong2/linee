from __future__ import annotations

from pathlib import Path

import redis
from django.conf import settings
from django.db import connection
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import never_cache


@never_cache
def health_live(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "ok"})


@never_cache
def health_ready(request: HttpRequest) -> JsonResponse:
    checks: dict[str, str] = {}
    failures: list[str] = []

    try:
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"
        failures.append("database")

    try:
        client = redis.Redis.from_url(
            settings.CACHES["default"]["LOCATION"],
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        client.ping()
        checks["cache"] = "ok"
    except Exception:
        checks["cache"] = "unavailable"
        failures.append("cache")

    status = 200 if not failures else 503
    payload = {
        "status": "ok" if not failures else "degraded",
        "checks": checks,
    }
    if settings.DEBUG and failures:
        payload["failed"] = failures
    return JsonResponse(payload, status=status)


def service_worker(request: HttpRequest) -> HttpResponse:
    path = Path(settings.BASE_DIR) / "static" / "js" / "service-worker.js"
    if not path.exists():
        raise Http404
    response = HttpResponse(
        path.read_text(encoding="utf-8"),
        content_type="application/javascript; charset=utf-8",
    )
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


def offline(request: HttpRequest) -> HttpResponse:
    return render(request, "public/offline.html", status=200)


def csrf_failure(request: HttpRequest, reason: str = "") -> HttpResponse:
    return render(
        request,
        "public/csrf_failure.html",
        {"reason": reason},
        status=403,
    )
