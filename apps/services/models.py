from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _

from apps.common.models import PublicIdModel, TimeStampedModel
from apps.organizations.models import Branch, Organization


class Service(TimeStampedModel):
    class Category(models.TextChoices):
        CONSULTATION = "consultation", _("Consultation")
        LABORATORY = "laboratory", _("Laboratory")
        MATERNAL_HEALTH = "maternal_health", _("Maternal health")
        PHARMACY = "pharmacy", _("Pharmacy")
        CIVIL_REGISTRY = "civil_registry", _("Civil registry")
        OTHER = "other", _("Other")

    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="services"
    )
    code = models.CharField(max_length=20)
    name_en = models.CharField(max_length=160)
    name_fr = models.CharField(max_length=160, blank=True)
    description_en = models.TextField(blank=True)
    description_fr = models.TextField(blank=True)
    category = models.CharField(
        max_length=30, choices=Category.choices, default=Category.CONSULTATION
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name_en",)
        constraints = [
            models.UniqueConstraint(
                fields=("organization", "code"),
                name="unique_service_code_per_org",
            )
        ]
        verbose_name = "service"
        verbose_name_plural = "services"

    def __str__(self) -> str:
        return f"{self.name_en} ({self.organization.name})"

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def display_name(self) -> str:
        if (get_language() or "").startswith("fr") and self.name_fr:
            return self.name_fr
        return self.name_en

    @property
    def display_description(self) -> str:
        if (get_language() or "").startswith("fr") and self.description_fr:
            return self.description_fr
        return self.description_en


class BranchService(TimeStampedModel, PublicIdModel):
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="branch_services"
    )
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="branch_services")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="branch_services")
    description_en = models.TextField(blank=True, help_text="Optional branch-specific description.")
    description_fr = models.TextField(blank=True)
    default_duration_minutes = models.PositiveIntegerField(default=15)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("branch__name", "service__name_en")
        constraints = [
            models.UniqueConstraint(
                fields=("branch", "service"),
                name="unique_branch_service",
            ),
            models.CheckConstraint(
                condition=models.Q(default_duration_minutes__gt=0),
                name="branch_service_duration_positive",
            ),
        ]
        verbose_name = "branch service"
        verbose_name_plural = "branch services"

    def __str__(self) -> str:
        return f"{self.service.name_en} — {self.branch.name}"

    def clean(self) -> None:
        super().clean()
        if self.branch_id and self.branch.organization_id != self.organization_id:
            raise ValidationError({"branch": "The branch must belong to the organization."})
        if self.service_id and self.service.organization_id != self.organization_id:
            raise ValidationError({"service": "The service must belong to the organization."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def display_name(self) -> str:
        return self.service.display_name

    @property
    def display_description(self) -> str:
        if (get_language() or "").startswith("fr") and self.description_fr:
            return self.description_fr
        return self.description_en or self.service.display_description

    @property
    def current_fee(self) -> ServiceFee | None:
        today = timezone.localdate()
        fees = list(self.fees.all())
        eligible = [
            fee
            for fee in fees
            if fee.is_active
            and fee.published_at is not None
            and fee.effective_from <= today
            and (fee.effective_to is None or fee.effective_to >= today)
        ]
        return max(eligible, key=lambda fee: fee.effective_from) if eligible else None


class ServiceFee(TimeStampedModel):
    class Currency(models.TextChoices):
        XAF = "XAF", "XAF"

    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="service_fees"
    )
    branch_service = models.ForeignKey(BranchService, on_delete=models.CASCADE, related_name="fees")
    amount_xaf = models.PositiveIntegerField(default=0)
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.XAF)
    effective_from = models.DateField(default=timezone.localdate)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    published_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="approved_service_fees",
    )

    class Meta:
        ordering = ("-effective_from",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gte=models.F("effective_from")),
                name="service_fee_valid_date_range",
            )
        ]
        indexes = [
            models.Index(
                fields=("branch_service", "effective_from"),
                name="fee_service_effective_idx",
            )
        ]
        verbose_name = "service fee"
        verbose_name_plural = "service fees"

    def __str__(self) -> str:
        return f"{self.branch_service} — {self.amount_xaf} {self.currency}"

    def clean(self) -> None:
        super().clean()
        if self.branch_service_id and self.branch_service.organization_id != self.organization_id:
            raise ValidationError(
                {"organization": "The fee must belong to the same organization as the service."}
            )
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValidationError({"effective_to": "The end date cannot be before the start date."})

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def is_current(self) -> bool:
        today = timezone.localdate()
        return (
            self.is_active
            and self.published_at is not None
            and self.effective_from <= today
            and (self.effective_to is None or self.effective_to >= today)
        )
