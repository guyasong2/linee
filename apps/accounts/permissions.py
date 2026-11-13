from __future__ import annotations

from django.db.models import QuerySet

from apps.organizations.models import Organization, OrganizationMembership

ACCESSIBLE_STATUSES = (Organization.Status.PENDING, Organization.Status.ACTIVE)


def memberships_for(user) -> QuerySet[OrganizationMembership]:
    if not getattr(user, "is_authenticated", False):
        return OrganizationMembership.objects.none()
    return (
        OrganizationMembership.objects.filter(
            user=user,
            is_active=True,
            organization__status__in=ACCESSIBLE_STATUSES,
        )
        .select_related("organization", "branch")
        .order_by("created_at")
    )


def primary_membership(user) -> OrganizationMembership | None:
    return memberships_for(user).first()


def membership_for(user, organization: Organization) -> OrganizationMembership | None:
    if not getattr(user, "is_authenticated", False):
        return None
    return (
        OrganizationMembership.objects.filter(
            user=user,
            organization=organization,
            is_active=True,
            organization__status__in=ACCESSIBLE_STATUSES,
        )
        .select_related("branch")
        .first()
    )
