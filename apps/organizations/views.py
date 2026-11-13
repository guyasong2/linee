from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from apps.accounts.permissions import membership_for
from apps.audit.services import record_audit
from apps.services.models import Service

from .forms import BranchForm, InviteMemberForm, OrganizationForm, ServiceForm
from .models import Branch, Organization, OrganizationMembership


def _require_admin(request, organization_slug):
    """Return (organization, membership) or raise Http404."""
    org = get_object_or_404(Organization, slug=organization_slug)
    membership = membership_for(request.user, org)
    if membership is None:
        raise Http404
    return org, membership


def _require_org_admin(request, organization_slug):
    """Return (organization, membership) or raise Http404 if not org admin."""
    org, membership = _require_admin(request, organization_slug)
    if membership.role != OrganizationMembership.Role.ORGANIZATION_ADMIN:
        raise Http404
    return org, membership


# ── Dashboard ────────────────────────────────────────────────────────


@login_required
def dashboard(request: HttpRequest, organization_slug: str) -> HttpResponse:
    org, membership = _require_admin(request, organization_slug)

    return render(
        request,
        "organizations/dashboard.html",
        {
            "organization": org,
            "membership": membership,
            "branch_count": org.branches.count(),
            "service_count": org.services.count(),
            "offering_count": org.branch_services.count(),
            "team_count": org.memberships.filter(is_active=True).count(),
        },
    )


# ── Organization profile ────────────────────────────────────────────


@login_required
def edit_organization(request: HttpRequest, organization_slug: str) -> HttpResponse:
    org, membership = _require_org_admin(request, organization_slug)

    before = {
        "name": org.name,
        "legal_name": org.legal_name,
        "organization_type": org.organization_type,
        "phone": org.phone,
        "email": org.email,
        "website": org.website,
        "city": org.city,
        "address": org.address,
    }

    form = OrganizationForm(request.POST or None, instance=org)
    if request.method == "POST" and form.is_valid():
        form.save()
        record_audit(
            action="organization.updated",
            resource_type="organization",
            organization=org,
            actor=request.user,
            resource_public_id=str(org.public_id),
            before=before,
            after={
                "name": org.name,
                "legal_name": org.legal_name,
                "organization_type": org.organization_type,
                "phone": org.phone,
                "email": org.email,
                "website": org.website,
                "city": org.city,
                "address": org.address,
            },
            request=request,
        )
        messages.success(request, _("Organization profile updated."))
        return redirect("organizations:dashboard", organization_slug=org.slug)

    return render(
        request,
        "organizations/edit_organization.html",
        {"organization": org, "membership": membership, "form": form},
    )


# ── Branches ─────────────────────────────────────────────────────────


@login_required
def branch_list(request: HttpRequest, organization_slug: str) -> HttpResponse:
    org, membership = _require_org_admin(request, organization_slug)
    branches = org.branches.order_by("name")

    return render(
        request,
        "organizations/branches.html",
        {"organization": org, "membership": membership, "branches": branches},
    )


@login_required
def branch_add(request: HttpRequest, organization_slug: str) -> HttpResponse:
    org, membership = _require_org_admin(request, organization_slug)

    form = BranchForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        branch = form.save(commit=False)
        branch.organization = org
        branch.save()
        record_audit(
            action="branch.created",
            resource_type="branch",
            organization=org,
            actor=request.user,
            resource_public_id=str(branch.public_id),
            after={"name": branch.name, "code": branch.code, "city": branch.city},
            request=request,
        )
        messages.success(request, _("Branch added."))
        return redirect("organizations:branches", organization_slug=org.slug)

    return render(
        request,
        "organizations/branch_form.html",
        {
            "organization": org,
            "membership": membership,
            "form": form,
            "editing": False,
        },
    )


@login_required
def branch_edit(request: HttpRequest, organization_slug: str, pk: int) -> HttpResponse:
    org, membership = _require_org_admin(request, organization_slug)
    branch = get_object_or_404(Branch, pk=pk, organization=org)

    before = {"name": branch.name, "code": branch.code, "status": branch.status}
    form = BranchForm(request.POST or None, instance=branch)
    if request.method == "POST" and form.is_valid():
        form.save()
        record_audit(
            action="branch.updated",
            resource_type="branch",
            organization=org,
            actor=request.user,
            resource_public_id=str(branch.public_id),
            before=before,
            after={"name": branch.name, "code": branch.code, "status": branch.status},
            request=request,
        )
        messages.success(request, _("Branch updated."))
        return redirect("organizations:branches", organization_slug=org.slug)

    return render(
        request,
        "organizations/branch_form.html",
        {
            "organization": org,
            "membership": membership,
            "form": form,
            "editing": True,
            "branch": branch,
        },
    )


# ── Services ─────────────────────────────────────────────────────────


@login_required
def service_list(request: HttpRequest, organization_slug: str) -> HttpResponse:
    org, membership = _require_org_admin(request, organization_slug)
    services = org.services.order_by("name_en")

    return render(
        request,
        "organizations/services.html",
        {"organization": org, "membership": membership, "services": services},
    )


@login_required
def service_add(request: HttpRequest, organization_slug: str) -> HttpResponse:
    org, membership = _require_org_admin(request, organization_slug)

    form = ServiceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        service = form.save(commit=False)
        service.organization = org
        service.save()
        record_audit(
            action="service.created",
            resource_type="service",
            organization=org,
            actor=request.user,
            resource_public_id=str(service.pk),
            after={
                "code": service.code,
                "name_en": service.name_en,
                "category": service.category,
            },
            request=request,
        )
        messages.success(request, _("Service added."))
        return redirect("organizations:services", organization_slug=org.slug)

    return render(
        request,
        "organizations/service_form.html",
        {
            "organization": org,
            "membership": membership,
            "form": form,
            "editing": False,
        },
    )


@login_required
def service_edit(request: HttpRequest, organization_slug: str, pk: int) -> HttpResponse:
    org, membership = _require_org_admin(request, organization_slug)
    service = get_object_or_404(Service, pk=pk, organization=org)

    before = {
        "code": service.code,
        "name_en": service.name_en,
        "category": service.category,
    }
    form = ServiceForm(request.POST or None, instance=service)
    if request.method == "POST" and form.is_valid():
        form.save()
        record_audit(
            action="service.updated",
            resource_type="service",
            organization=org,
            actor=request.user,
            resource_public_id=str(service.pk),
            before=before,
            after={
                "code": service.code,
                "name_en": service.name_en,
                "category": service.category,
            },
            request=request,
        )
        messages.success(request, _("Service updated."))
        return redirect("organizations:services", organization_slug=org.slug)

    return render(
        request,
        "organizations/service_form.html",
        {
            "organization": org,
            "membership": membership,
            "form": form,
            "editing": True,
            "service": service,
        },
    )


# ── Team ─────────────────────────────────────────────────────────────


@login_required
def team_list(request: HttpRequest, organization_slug: str) -> HttpResponse:
    org, membership = _require_org_admin(request, organization_slug)
    members = (
        org.memberships.filter(is_active=True)
        .select_related("user", "branch")
        .order_by("user__full_name")
    )

    return render(
        request,
        "organizations/team.html",
        {"organization": org, "membership": membership, "members": members},
    )


@login_required
def team_invite(request: HttpRequest, organization_slug: str) -> HttpResponse:
    org, membership = _require_org_admin(request, organization_slug)

    form = InviteMemberForm(request.POST or None, organization=org)
    if request.method == "POST" and form.is_valid():
        user = form.resolve_user()
        if user is None:
            form.add_error(
                "identifier",
                _(
                    "No account found with this phone number or email. "
                    "The person must create an account first."
                ),
            )
        elif org.memberships.filter(user=user, is_active=True).exists():
            form.add_error(
                "identifier",
                _("This person is already a member of this organization."),
            )
        else:
            role = form.cleaned_data["role"]
            branch = form.cleaned_data.get("branch")
            member = OrganizationMembership.objects.create(
                organization=org,
                user=user,
                role=role,
                branch=branch,
            )
            record_audit(
                action="membership.created",
                resource_type="membership",
                organization=org,
                actor=request.user,
                resource_public_id=str(member.pk),
                after={
                    "user": str(user),
                    "role": role,
                    "branch": str(branch) if branch else None,
                },
                request=request,
            )
            messages.success(request, _("Team member added."))
            return redirect("organizations:team", organization_slug=org.slug)

    return render(
        request,
        "organizations/team_invite.html",
        {"organization": org, "membership": membership, "form": form},
    )


@login_required
def team_remove(request: HttpRequest, organization_slug: str, pk: int) -> HttpResponse:
    org, membership = _require_org_admin(request, organization_slug)

    if request.method != "POST":
        raise Http404

    member = get_object_or_404(OrganizationMembership, pk=pk, organization=org, is_active=True)

    # Cannot remove yourself
    if member.user == request.user:
        messages.error(request, _("You cannot remove yourself from the organization."))
        return redirect("organizations:team", organization_slug=org.slug)

    member.is_active = False
    member.save(update_fields=["is_active"])

    record_audit(
        action="membership.deactivated",
        resource_type="membership",
        organization=org,
        actor=request.user,
        resource_public_id=str(member.pk),
        after={"user": str(member.user), "role": member.role, "is_active": False},
        request=request,
    )
    messages.success(request, _("Team member removed."))
    return redirect("organizations:team", organization_slug=org.slug)
