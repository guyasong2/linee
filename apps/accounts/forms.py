from __future__ import annotations

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _

from apps.organizations.models import Organization, OrganizationMembership

from .models import User
from .validators import normalize_email, normalize_phone

INPUT_CLASS = "form-input"
SELECT_CLASS = "form-select"


def _text_attrs(autocomplete: str = "", **extra) -> dict:
    attrs = {"class": INPUT_CLASS}
    if autocomplete:
        attrs["autocomplete"] = autocomplete
    attrs.update(extra)
    return attrs


class PersonSignUpForm(forms.Form):
    full_name = forms.CharField(
        max_length=150,
        label=_("Full name"),
        widget=forms.TextInput(attrs=_text_attrs("name", placeholder=_("Your name"))),
    )
    phone = forms.CharField(
        max_length=30,
        required=False,
        label=_("Phone number"),
        widget=forms.TextInput(attrs=_text_attrs("tel", placeholder=_("+237 6 00 00 00 00"))),
    )
    email = forms.EmailField(
        required=False,
        label=_("Email address"),
        widget=forms.EmailInput(attrs=_text_attrs("email", placeholder=_("you@example.com"))),
    )
    preferred_language = forms.ChoiceField(
        label=_("Preferred language"),
        choices=User.Language.choices,
        initial=User.Language.ENGLISH,
        widget=forms.Select(attrs={"class": SELECT_CLASS}),
    )
    password1 = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs=_text_attrs("new-password")),
        help_text=_("Use at least 12 characters."),
    )
    password2 = forms.CharField(
        label=_("Confirm password"),
        widget=forms.PasswordInput(attrs=_text_attrs("new-password")),
    )
    accept_terms = forms.BooleanField(
        label=_("I agree to the privacy notice."),
        widget=forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        error_messages={
            "required": _("Accept the privacy notice to create an account."),
        },
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.fields["preferred_language"].initial = (get_language() or "en")[:2]

    def clean_phone(self):
        try:
            return normalize_phone(self.cleaned_data.get("phone"))
        except ValidationError as exc:
            raise forms.ValidationError(exc.messages) from exc

    def clean_email(self):
        try:
            return normalize_email(self.cleaned_data.get("email"))
        except ValidationError as exc:
            raise forms.ValidationError(exc.messages) from exc

    def clean(self):
        cleaned = super().clean()
        phone = cleaned.get("phone")
        email = cleaned.get("email")

        if not phone and not email:
            raise forms.ValidationError(_("Enter a phone number or an email address."))
        if phone and User.objects.filter(phone=phone).exists():
            self.add_error("phone", _("An account with this phone number already exists."))
        if email and User.objects.filter(email=email).exists():
            self.add_error("email", _("An account with this email address already exists."))

        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", _("The two passwords do not match."))
        elif password1:
            provisional = User(phone=phone, email=email, full_name=cleaned.get("full_name"))
            try:
                validate_password(password1, provisional)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned

    def save(self) -> User:
        return User.objects.create_user(
            phone=self.cleaned_data["phone"],
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password1"],
            full_name=self.cleaned_data["full_name"].strip(),
            preferred_language=self.cleaned_data["preferred_language"],
        )


class OrganizationSignUpForm(forms.Form):
    organization_name = forms.CharField(
        max_length=180,
        label=_("Organization name"),
        widget=forms.TextInput(
            attrs=_text_attrs("organization", placeholder=_("Example: Douala General Hospital"))
        ),
    )
    organization_type = forms.ChoiceField(
        label=_("Organization type"),
        choices=[("", _("Select a type"))] + list(Organization.Type.choices),
        widget=forms.Select(attrs={"class": SELECT_CLASS}),
    )
    city = forms.CharField(
        max_length=80,
        initial="Douala",
        label=_("City"),
        widget=forms.TextInput(attrs=_text_attrs("address-level2")),
    )
    address = forms.CharField(
        max_length=220,
        required=False,
        label=_("Street address"),
        widget=forms.TextInput(attrs=_text_attrs("street-address")),
    )
    organization_phone = forms.CharField(
        max_length=30,
        required=False,
        label=_("Organization phone"),
        widget=forms.TextInput(attrs=_text_attrs("tel")),
    )
    organization_email = forms.EmailField(
        required=False,
        label=_("Organization email"),
        widget=forms.EmailInput(attrs=_text_attrs("email")),
    )
    admin_full_name = forms.CharField(
        max_length=150,
        label=_("Your full name"),
        widget=forms.TextInput(attrs=_text_attrs("name")),
    )
    admin_phone = forms.CharField(
        max_length=30,
        required=False,
        label=_("Your phone number"),
        widget=forms.TextInput(attrs=_text_attrs("tel", placeholder=_("+237 6 00 00 00 00"))),
    )
    admin_email = forms.EmailField(
        required=False,
        label=_("Your email address"),
        widget=forms.EmailInput(attrs=_text_attrs("email", placeholder=_("you@example.com"))),
    )
    preferred_language = forms.ChoiceField(
        label=_("Preferred language"),
        choices=User.Language.choices,
        initial=User.Language.ENGLISH,
        widget=forms.Select(attrs={"class": SELECT_CLASS}),
    )
    password1 = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs=_text_attrs("new-password")),
        help_text=_("Use at least 12 characters."),
    )
    password2 = forms.CharField(
        label=_("Confirm password"),
        widget=forms.PasswordInput(attrs=_text_attrs("new-password")),
    )
    accept_terms = forms.BooleanField(
        label=_("I agree to the privacy notice."),
        widget=forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        error_messages={
            "required": _("Accept the privacy notice to register an organization."),
        },
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.fields["preferred_language"].initial = (get_language() or "en")[:2]

    def _normalized_phone(self, field_name: str):
        try:
            return normalize_phone(self.cleaned_data.get(field_name))
        except ValidationError as exc:
            self.add_error(field_name, exc)
            return None

    def clean_organization_phone(self):
        return self._normalized_phone("organization_phone")

    def clean_admin_phone(self):
        return self._normalized_phone("admin_phone")

    def clean_organization_email(self):
        try:
            return normalize_email(self.cleaned_data.get("organization_email"))
        except ValidationError as exc:
            raise forms.ValidationError(exc.messages) from exc

    def clean_admin_email(self):
        try:
            return normalize_email(self.cleaned_data.get("admin_email"))
        except ValidationError as exc:
            raise forms.ValidationError(exc.messages) from exc

    def clean(self):
        cleaned = super().clean()
        org_phone = cleaned.get("organization_phone")
        org_email = cleaned.get("organization_email")
        admin_phone = cleaned.get("admin_phone")
        admin_email = cleaned.get("admin_email")

        if not org_phone and not org_email:
            raise forms.ValidationError(
                _(
                    "Add at least one contact for the organization: a phone number or an email address."
                )
            )
        if not admin_phone and not admin_email:
            raise forms.ValidationError(
                _("Enter a phone number or an email address for your administrator account.")
            )
        if admin_phone and User.objects.filter(phone=admin_phone).exists():
            self.add_error(
                "admin_phone",
                _("An account with this phone number already exists. Sign in instead."),
            )
        if admin_email and User.objects.filter(email=admin_email).exists():
            self.add_error(
                "admin_email",
                _("An account with this email address already exists. Sign in instead."),
            )

        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", _("The two passwords do not match."))
        elif password1:
            provisional = User(
                phone=admin_phone,
                email=admin_email,
                full_name=cleaned.get("admin_full_name"),
            )
            try:
                validate_password(password1, provisional)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned

    @transaction.atomic
    def save(self) -> tuple[User, Organization]:
        data = self.cleaned_data
        user = User.objects.create_user(
            phone=data["admin_phone"],
            email=data["admin_email"],
            password=data["password1"],
            full_name=data["admin_full_name"].strip(),
            preferred_language=data["preferred_language"],
        )
        organization = Organization.objects.create(
            name=data["organization_name"].strip(),
            organization_type=data["organization_type"],
            city=data["city"].strip(),
            address=data["address"].strip(),
            phone=data["organization_phone"] or "",
            email=data["organization_email"] or "",
            default_language=data["preferred_language"],
        )
        OrganizationMembership.objects.create(
            organization=organization,
            user=user,
            role=OrganizationMembership.Role.ORGANIZATION_ADMIN,
        )
        return user, organization


class LineeAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label=_("Phone or email"),
        widget=forms.TextInput(
            attrs=_text_attrs("username", autofocus=True, placeholder=_("Phone or email"))
        ),
    )
    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs=_text_attrs("current-password")),
    )

    error_messages = {
        "invalid_login": _("The phone number or email and password do not match an account."),
        "inactive": _("This account is inactive."),
    }
