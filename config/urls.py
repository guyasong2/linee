from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path

from apps.common.views import health_live, health_ready, offline, service_worker

admin.site.site_header = "Linee platform administration"
admin.site.site_title = "Linee administration"
admin.site.index_title = "Operations"


def root_redirect(request):
    language = request.LANGUAGE_CODE or settings.LANGUAGE_CODE
    return redirect(f"/{language}/")


urlpatterns = [
    path("", root_redirect, name="root"),
    path("admin/", admin.site.urls),
    path("health/live/", health_live, name="health_live"),
    path("health/ready/", health_ready, name="health_ready"),
    path("service-worker.js", service_worker, name="service_worker"),
    path("i18n/", include("django.conf.urls.i18n")),
]

urlpatterns += i18n_patterns(
    path("", include("apps.public.urls")),
    path("", include("apps.accounts.urls")),
    path("find/", include("apps.services.urls")),
    path("manage/", include("apps.organizations.urls")),
    path("offline/", offline, name="offline"),
    prefix_default_language=True,
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = "apps.public.views.not_found"
handler500 = "apps.public.views.server_error"
