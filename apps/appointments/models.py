from __future__ import annotations

import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.checklists.models import ChecklistAcknowledgement
from apps.common.models import PublicIdModel, TimeStampedModel
from apps.organizations.models import Branch, Organization
from apps.services.models import BranchService


def generate_appointment_reference() -> str:
    """Generate a clean, unambiguous appointment reference like APT-7F8K-9M2X."""
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    part1 = "".join(secrets.choice(chars) for _ in range(4))
    part2 = "".join(secrets.choice(chars) for _ in range(4))
    return f"APT-{part1}-{part2}"


class AppointmentSlot(TimeStampedModel):
    branch_service = models.ForeignKey(
        BranchService, on_delete=models.CASCADE, related_name="appointment_slots"
    )
    date = models.DateField(db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    capacity = models.PositiveIntegerField(default=1)
    booked_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("date", "start_time")
        constraints = [
            models.UniqueConstraint(
                fields=("branch_service", "date", "start_time"),
                name="unique_slot_per_service_time",
            ),
            models.CheckConstraint(
                condition=models.Q(end_time__gt=models.F("start_time")),
                name="slot_end_time_after_start",
            ),
        ]
        verbose_name = "appointment slot"
        verbose_name_plural = "appointment slots"

    def __str__(self) -> str:
        return f"{self.branch_service} - {self.date} {self.start_time.strftime('%H:%M')} ({self.booked_count}/{self.capacity})"

    @property
    def has_availability(self) -> bool:
        return self.is_active and self.booked_count < self.capacity

    @property
    def available_capacity(self) -> int:
        return max(0, self.capacity - self.booked_count)


class Appointment(TimeStampedModel, PublicIdModel):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", _("Confirmed")
        CHECKED_IN = "checked_in", _("Checked in")
        COMPLETED = "completed", _("Completed")
        CANCELLED = "cancelled", _("Cancelled")
        NO_SHOW = "no_show", _("No show")

    reference = models.CharField(
        max_length=20, unique=True, default=generate_appointment_reference, db_index=True
    )
    organization = models.ForeignKey(
        Organization, on_delete=models.PROTECT, related_name="appointments"
    )
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="appointments")
    branch_service = models.ForeignKey(
        BranchService, on_delete=models.PROTECT, related_name="appointments"
    )
    slot = models.ForeignKey(AppointmentSlot, on_delete=models.PROTECT, related_name="appointments")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointments",
    )
    customer_name = models.CharField(max_length=150)
    customer_phone = models.CharField(max_length=30, blank=True)
    customer_email = models.EmailField(blank=True)

    checklist_acknowledgement = models.ForeignKey(
        ChecklistAcknowledgement,
        on_delete=models.PROTECT,
        related_name="appointments",
        null=True,
        blank=True,
        help_text="Mandatory acknowledgement token validating customer readiness.",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.CONFIRMED, db_index=True
    )
    appointment_date = models.DateField(db_index=True)
    scheduled_time = models.TimeField()
    checked_in_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.CharField(max_length=250, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("appointment_date", "scheduled_time")
        indexes = [
            models.Index(fields=("organization", "appointment_date", "status")),
            models.Index(fields=("user", "status")),
        ]
        verbose_name = "appointment"
        verbose_name_plural = "appointments"

    def __str__(self) -> str:
        return f"{self.reference} - {self.customer_name} ({self.appointment_date} {self.scheduled_time.strftime('%H:%M')})"

    def clean(self) -> None:
        super().clean()
        if self.branch_service_id and self.branch_service.organization_id != self.organization_id:
            raise ValidationError(
                {"branch_service": "Service does not belong to the organization."}
            )
        if self.branch_id and self.branch.organization_id != self.organization_id:
            raise ValidationError({"branch": "Branch does not belong to the organization."})

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = generate_appointment_reference()
        super().save(*args, **kwargs)
