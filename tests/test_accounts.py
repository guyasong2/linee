from __future__ import annotations

import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.organizations.models import Organization, OrganizationMembership

PASSWORD = "LineeDemoPass2026!"


def person_payload(**overrides):
    data = {
        "full_name": "Amina Njoya",
        "phone": "+237 6 71 23 45 67",
        "email": "amina@example.com",
        "preferred_language": "en",
        "password1": PASSWORD,
        "password2": PASSWORD,
        "accept_terms": "on",
    }
    data.update(overrides)
    return data


def organization_payload(**overrides):
    data = {
        "organization_name": "Bonanjo Health Centre",
        "organization_type": "clinic",
        "city": "Douala",
        "address": "12 Rue Bonanjo",
        "organization_phone": "+237 6 71 23 45 68",
        "organization_email": "contact@bonanjo.example",
        "admin_full_name": "Paul Mballa",
        "admin_phone": "+237 6 71 23 45 69",
        "admin_email": "paul@example.com",
        "preferred_language": "fr",
        "password1": PASSWORD,
        "password2": PASSWORD,
        "accept_terms": "on",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
class TestRegistration:
    def test_auth_pages_render(self, client):
        for name in (
            "accounts:login",
            "accounts:register",
            "accounts:register_person",
            "accounts:register_organization",
        ):
            response = client.get(reverse(name))
            assert response.status_code == 200

    def test_person_signup_creates_account_and_signs_in(self, client):
        response = client.post(reverse("accounts:register_person"), person_payload())

        assert response.status_code == 302
        assert response["Location"] == reverse("accounts:account")
        user = User.objects.get(email="amina@example.com")
        assert user.phone == "+237671234567"
        assert user.check_password(PASSWORD)
        assert client.session["_auth_user_id"] == str(user.pk)
        assert AuditLog.objects.filter(action="account.registered", actor=user).exists()

    def test_person_signup_requires_a_contact(self, client):
        response = client.post(
            reverse("accounts:register_person"),
            person_payload(phone="", email=""),
        )

        assert response.status_code == 200
        assert "Enter a phone number or an email address." in response.content.decode()
        assert not User.objects.exists()

    def test_organization_signup_creates_pending_tenant_and_admin(self, client):
        response = client.post(reverse("accounts:register_organization"), organization_payload())

        organization = Organization.objects.get(name="Bonanjo Health Centre")
        assert response.status_code == 302
        assert response["Location"] == reverse("organizations:dashboard", args=[organization.slug])
        assert organization.status == Organization.Status.PENDING
        assert organization.organization_type == Organization.Type.CLINIC
        membership = organization.memberships.get()
        assert membership.role == OrganizationMembership.Role.ORGANIZATION_ADMIN
        assert membership.user.email == "paul@example.com"
        assert membership.branch is None
        assert AuditLog.objects.filter(
            action="organization.registered", organization=organization
        ).exists()

        dashboard = client.get(response["Location"])
        assert dashboard.status_code == 200
        assert "Bonanjo Health Centre" in dashboard.content.decode()

    def test_organization_names_get_unique_slugs(self):
        first = Organization.objects.create(name="Central Hospital")
        second = Organization.objects.create(name="Central Hospital")

        assert first.slug == "central-hospital"
        assert second.slug == "central-hospital-2"


@pytest.mark.django_db
class TestAuthentication:
    @pytest.fixture
    def user(self):
        return User.objects.create_user(
            phone="+237671234570",
            email="person@example.com",
            password=PASSWORD,
            full_name="Person Example",
        )

    def test_login_with_phone(self, client, user):
        response = client.post(
            reverse("accounts:login"),
            {"username": "+237 6 71 23 45 70", "password": PASSWORD},
        )

        assert response.status_code == 302
        assert response["Location"] == reverse("accounts:account")
        assert client.session["_auth_user_id"] == str(user.pk)

    def test_login_with_email(self, client, user):
        response = client.post(
            reverse("accounts:login"),
            {"username": "PERSON@EXAMPLE.COM", "password": PASSWORD},
        )

        assert response.status_code == 302
        assert client.session["_auth_user_id"] == str(user.pk)

    def test_invalid_login_stays_on_form(self, client, user):
        response = client.post(
            reverse("accounts:login"),
            {"username": user.phone, "password": "wrong-password"},
        )

        assert response.status_code == 200
        assert "_auth_user_id" not in client.session
        assert "do not match an account" in response.content.decode()

    def test_account_requires_authentication(self, client):
        response = client.get(reverse("accounts:account"))

        assert response.status_code == 302
        assert reverse("accounts:login") in response["Location"]

    def test_logout_requires_post(self, client, user):
        client.force_login(user)

        get_response = client.get(reverse("accounts:logout"))
        assert get_response.status_code == 405

        post_response = client.post(reverse("accounts:logout"))
        assert post_response.status_code == 302
        assert "_auth_user_id" not in client.session


@pytest.mark.django_db
class TestTenantIsolation:
    @pytest.fixture
    def tenants(self):
        first_user = User.objects.create_user(
            phone="+237671234571", password=PASSWORD, full_name="First Admin"
        )
        second_user = User.objects.create_user(
            phone="+237671234572", password=PASSWORD, full_name="Second Admin"
        )
        first = Organization.objects.create(name="First Hospital")
        second = Organization.objects.create(name="Second Hospital")
        OrganizationMembership.objects.create(
            organization=first,
            user=first_user,
            role=OrganizationMembership.Role.ORGANIZATION_ADMIN,
        )
        OrganizationMembership.objects.create(
            organization=second,
            user=second_user,
            role=OrganizationMembership.Role.ORGANIZATION_ADMIN,
        )
        return first_user, first, second

    def test_member_can_open_own_workspace(self, client, tenants):
        first_user, first, _ = tenants
        client.force_login(first_user)

        response = client.get(reverse("organizations:dashboard", args=[first.slug]))

        assert response.status_code == 200

    def test_member_cannot_open_another_tenant(self, client, tenants):
        first_user, _, second = tenants
        client.force_login(first_user)

        response = client.get(reverse("organizations:dashboard", args=[second.slug]))

        assert response.status_code == 404

    def test_organization_login_lands_in_workspace(self, client, tenants):
        first_user, first, _ = tenants

        response = client.post(
            reverse("accounts:login"),
            {"username": first_user.phone, "password": PASSWORD},
        )

        assert response.status_code == 302
        assert response["Location"] == reverse("organizations:dashboard", args=[first.slug])
