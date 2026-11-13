from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from apps.accounts.permissions import membership_for

from .models import Organization


@login_required
def dashboard(request: HttpRequest, organization_slug: str) -> HttpResponse:
    organization = get_object_or_404(Organization, slug=organization_slug)
    membership = membership_for(request.user, organization)
    if membership is None:
        raise Http404

    return render(
        request,
        "organizations/dashboard.html",
        {
            "organization": organization,
            "membership": membership,
            "branch_count": organization.branches.count(),
            "service_count": organization.branch_services.count(),
            "team_count": organization.memberships.filter(is_active=True).count(),
        },
    )
