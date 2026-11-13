from __future__ import annotations

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import User
from apps.accounts.validators import normalize_email, normalize_phone
from apps.services.models import Service

from .models import Branch, Organization, OrganizationMembership

INPUT_CLASS = "form-input"
SELECT_CLASS = "form-select"


class OrganizationForm(forms.ModelForm):
    website = forms.URLField(
        required=False,
        assume_scheme="https",
        widget=forms.URLInput(attrs={"class": INPUT_CLASS, "placeholder": "https://"}),
    )

    class Meta:
        model = Organization
        fields = (
            "name",
            "legal_name",
            "organization_type",
            "phone",
            "email",
            "website",
            "city",
            "address",
            "timezone",
            "default_language",
        )
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "legal_name": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "organization_type": forms.Select(attrs={"class": SELECT_CLASS}),
            "phone": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "email": forms.EmailInput(attrs={"class": INPUT_CLASS}),
            "website": forms.URLInput(attrs={"class": INPUT_CLASS, "placeholder": "https://"}),
            "city": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "address": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "timezone": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "default_language": forms.Select(attrs={"class": SELECT_CLASS}),
        }


class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = (
            "name",
            "code",
            "status",
            "phone",
            "email",
            "city",
            "address",
        )
        widgets = {
            "name": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "code": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "e.g. BON"}),
            "status": forms.Select(attrs={"class": SELECT_CLASS}),
            "phone": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "email": forms.EmailInput(attrs={"class": INPUT_CLASS}),
            "city": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "address": forms.TextInput(attrs={"class": INPUT_CLASS}),
        }


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = (
            "code",
            "name_en",
            "name_fr",
            "description_en",
            "description_fr",
            "category",
            "is_active",
        )
        widgets = {
            "code": forms.TextInput(attrs={"class": INPUT_CLASS, "placeholder": "e.g. CONS"}),
            "name_en": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "name_fr": forms.TextInput(attrs={"class": INPUT_CLASS}),
            "description_en": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
            "description_fr": forms.Textarea(attrs={"class": INPUT_CLASS, "rows": 3}),
            "category": forms.Select(attrs={"class": SELECT_CLASS}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-checkbox"}),
        }
        labels = {
            "name_en": _("Name (English)"),
            "name_fr": _("Name (French)"),
            "description_en": _("Description (English)"),
            "description_fr": _("Description (French)"),
        }


class InviteMemberForm(forms.Form):
    identifier = forms.CharField(
        max_length=150,
        label=_("Phone or email"),
        help_text=_("Enter the phone number or email address of the person to invite."),
        widget=forms.TextInput(attrs={"class": INPUT_CLASS}),
    )
    role = forms.ChoiceField(
        choices=OrganizationMembership.Role.choices,
        label=_("Role"),
        widget=forms.Select(attrs={"class": SELECT_CLASS}),
    )
    branch = forms.ModelChoiceField(
        queryset=Branch.objects.none(),
        required=False,
        label=_("Branch"),
        help_text=_("Required for Agent, Counter staff, and Branch manager roles."),
        widget=forms.Select(attrs={"class": SELECT_CLASS}),
    )

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            self.fields["branch"].queryset = Branch.objects.filter(
                organization=organization, status=Branch.Status.ACTIVE
            )

    def clean_identifier(self):
        value = self.cleaned_data["identifier"].strip()
        if "@" in value:
            try:
                return normalize_email(value)
            except ValidationError as exc:
                raise forms.ValidationError(exc.messages) from exc
        else:
            try:
                return normalize_phone(value)
            except ValidationError as exc:
                raise forms.ValidationError(exc.messages) from exc

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get("role")
        branch = cleaned.get("branch")
        branch_roles = {
            OrganizationMembership.Role.AGENT,
            OrganizationMembership.Role.COUNTER_STAFF,
            OrganizationMembership.Role.BRANCH_MANAGER,
        }
        if role in branch_roles and not branch:
            self.add_error("branch", _("This role requires a branch to be selected."))
        return cleaned

    def resolve_user(self):
        """Find the user matching the identifier, or None."""
        identifier = self.cleaned_data["identifier"]
        if "@" in identifier:
            return User.objects.filter(email=identifier).first()
        return User.objects.filter(phone=identifier).first()
