from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from apps.common.models import PublicIdModel, TimeStampedModel


class Organization(TimeStampedModel, PublicIdModel):
    class Status(models.TextChoices):
        PENDING = "pending", _("Pending setup")
        ACTIVE = "active", _("Active")
        SUSPENDED = "suspended", _("Suspended")

    class Language(models.TextChoices):
        ENGLISH = "en", _("English")
        FRENCH = "fr", _("Français")

    class Type(models.TextChoices):
        HOSPITAL = "hospital", _("Hospital")
        CLINIC = "clinic", _("Clinic")
        GOVERNMENT = "government", _("Government office")
        CIVIL_REGISTRY = "civil_registry", _("Civil registry")
        BANK = "bank", _("Bank")
        OTHER = "other", _("Other institution")

    name = models.CharField(max_length=180)
    slug = models.SlugField(max_length=80, unique=True)
    legal_name = models.CharField(max_length=220, blank=True)
    organization_type = models.CharField(max_length=30, choices=Type.choices, default=Type.OTHER)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    timezone = models.CharField(max_length=64, default="Africa/Douala")
    default_language = models.CharField(
        max_length=2, choices=Language.choices, default=Language.ENGLISH
    )
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    city = models.CharField(max_length=80, default="Douala")
    address = models.CharField(max_length=220, blank=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "organization"
        verbose_name_plural = "organizations"

    def __str__(self) -> str:
        return self.name

    def _unique_slug(self) -> str:
        base = slugify(self.name)[:70].strip("-") or "organization"
        candidate = base
        suffix = 2
        while Organization.objects.filter(slug=candidate).exclude(pk=self.pk).exists():
            candidate = f"{base}-{suffix}"
            suffix += 1
        return candidate

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._unique_slug()
        super().save(*args, **kwargs)


class Branch(TimeStampedModel, PublicIdModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        TEMPORARILY_CLOSED = "temporarily_closed", "Temporarily closed"
        CLOSED = "closed", "Closed"

    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="branches"
    )
    name = models.CharField(max_length=180)
    code = models.CharField(max_length=20)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.ACTIVE)
    timezone = models.CharField(max_length=64, default="Africa/Douala")
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    city = models.CharField(max_length=80, default="Douala")
    address = models.CharField(max_length=220, blank=True)

    class Meta:
        ordering = ("organization__name", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="unique_branch_code_per_org",
            )
        ]
        verbose_name = "branch"
        verbose_name_plural = "branches"

    def __str__(self) -> str:
        return f"{self.name} ({self.organization.name})"

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)


class OrganizationMembership(TimeStampedModel):
    class Role(models.TextChoices):
        AGENT = "agent", "Agent"
        COUNTER_STAFF = "counter_staff", "Counter staff"
        BRANCH_MANAGER = "branch_manager", "Branch manager"
        ORGANIZATION_ADMIN = "organization_admin", "Organization administrator"

    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="memberships"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.PROTECT,
        related_name="memberships",
        null=True,
        blank=True,
        help_text="Leave empty for an organization-wide administrator.",
    )
    role = models.CharField(max_length=30, choices=Role.choices)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("organization__name", "user__full_name")
        constraints = [
            models.UniqueConstraint(
                fields=("user", "organization"),
                name="unique_membership_per_user_org",
            )
        ]
        verbose_name = "organization membership"
        verbose_name_plural = "organization memberships"

    def __str__(self) -> str:
        return f"{self.user} — {self.get_role_display()}"

    def clean(self) -> None:
        super().clean()
        if self.branch_id and self.branch.organization_id != self.organization_id:
            raise ValidationError({"branch": "The branch must belong to the organization."})

        branch_roles = {
            self.Role.AGENT,
            self.Role.COUNTER_STAFF,
            self.Role.BRANCH_MANAGER,
        }
        if self.role in branch_roles and not self.branch_id:
            raise ValidationError({"branch": "This role must be scoped to a branch."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
