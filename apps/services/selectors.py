from __future__ import annotations

from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.organizations.models import Branch, Organization

from .models import BranchService, Service


def active_branch_services() -> QuerySet[BranchService]:
    today = timezone.localdate()
    return (
        BranchService.objects.filter(
            is_active=True,
            branch__status=Branch.Status.ACTIVE,
            branch__organization__status=Organization.Status.ACTIVE,
            service__is_active=True,
            fees__is_active=True,
            fees__published_at__isnull=False,
            fees__effective_from__lte=today,
        )
        .filter(Q(fees__effective_to__isnull=True) | Q(fees__effective_to__gte=today))
        .select_related("organization", "branch", "service")
        .prefetch_related("fees")
        .distinct()
    )


def search_branch_services(
    query: str = "", category: str = ""
) -> QuerySet[BranchService]:
    queryset = active_branch_services()
    if query:
        queryset = queryset.filter(
            Q(service__name_en__icontains=query)
            | Q(service__name_fr__icontains=query)
            | Q(service__code__icontains=query)
            | Q(branch__name__icontains=query)
            | Q(branch__city__icontains=query)
            | Q(organization__name__icontains=query)
        )
    if category:
        queryset = queryset.filter(service__category=category)
    return queryset.order_by("branch__name", "service__name_en")


def service_categories() -> list[tuple[str, str]]:
    return list(Service.Category.choices)
