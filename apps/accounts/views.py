from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.audit.services import record_audit

from .forms import LineeAuthenticationForm, OrganizationSignUpForm, PersonSignUpForm
from .permissions import memberships_for, primary_membership


def _safe_next(request: HttpRequest, fallback: str) -> str:
    candidate = request.POST.get("next") or request.GET.get("next") or ""
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return fallback


def _landing_url(user) -> str:
    membership = primary_membership(user)
    if membership is not None:
        return reverse("organizations:dashboard", args=[membership.organization.slug])
    if getattr(user, "is_platform_admin", False) or getattr(user, "is_superuser", False):
        return reverse("admin:index")
    return reverse("accounts:account")


def register(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect(_landing_url(request.user))
    return render(request, "accounts/register_choice.html")


def register_person(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect(_landing_url(request.user))

    form = PersonSignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(
            request,
            user,
            backend="apps.accounts.backends.EmailOrPhoneBackend",
        )
        record_audit(
            action="account.registered",
            resource_type="user",
            actor=user,
            resource_public_id=str(user.pk),
            after={
                "full_name": user.full_name,
                "phone": user.phone,
                "email": user.email,
                "preferred_language": user.preferred_language,
                "account_type": "personal",
            },
            request=request,
        )
        messages.success(request, _("Your account is ready."))
        return redirect(_safe_next(request, reverse("accounts:account")))

    return render(request, "accounts/register_person.html", {"form": form})


def register_organization(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect(_landing_url(request.user))

    form = OrganizationSignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user, organization = form.save()
        login(
            request,
            user,
            backend="apps.accounts.backends.EmailOrPhoneBackend",
        )
        record_audit(
            action="organization.registered",
            resource_type="organization",
            organization=organization,
            actor=user,
            resource_public_id=organization.public_id,
            after={
                "name": organization.name,
                "organization_type": organization.organization_type,
                "city": organization.city,
                "status": organization.status,
                "administrator": user.full_name,
            },
            request=request,
        )
        messages.success(
            request,
            _("Organization registered. Complete the setup steps before it can appear publicly."),
        )
        return redirect(
            _safe_next(
                request,
                reverse("organizations:dashboard", args=[organization.slug]),
            )
        )

    return render(request, "accounts/register_organization.html", {"form": form})


def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect(_landing_url(request.user))

    form = LineeAuthenticationForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)
        record_audit(
            action="auth.login",
            resource_type="user",
            actor=user,
            resource_public_id=str(user.pk),
            request=request,
        )
        return redirect(_safe_next(request, _landing_url(user)))

    return render(request, "accounts/login.html", {"form": form})


@require_POST
def logout_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        record_audit(
            action="auth.logout",
            resource_type="user",
            actor=request.user,
            resource_public_id=str(request.user.pk),
            request=request,
        )
    logout(request)
    messages.success(request, _("You have signed out."))
    return redirect("public:home")


@login_required
def account(request: HttpRequest) -> HttpResponse:
    memberships = memberships_for(request.user)
    return render(
        request,
        "accounts/account.html",
        {"memberships": memberships},
    )
