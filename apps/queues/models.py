from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.checklists.models import ChecklistAcknowledgement
from apps.common.models import PublicIdModel, TimeStampedModel
from apps.organizations.models import Branch, Counter, Organization
from apps.services.models import BranchService


class Queue(TimeStampedModel, PublicIdModel):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name="queues")
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="queues")
    branch_service = models.ForeignKey(
        BranchService, on_delete=models.CASCADE, related_name="queues", null=True, blank=True
    )
    name = models.CharField(max_length=120)
    prefix = models.CharField(max_length=5, default="A")
    is_active = models.BooleanField(default=True)
    is_paused = models.BooleanField(default=False)
    max_daily_capacity = models.PositiveIntegerField(default=150)
    current_sequence = models.PositiveIntegerField(default=0)
    date = models.DateField(default=timezone.localdate, db_index=True)

    class Meta:
        ordering = ("branch__name", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("branch", "prefix", "date"),
                name="unique_queue_prefix_per_branch_date",
            )
        ]
        verbose_name = "queue"
        verbose_name_plural = "queues"

    def __str__(self) -> str:
        return f"{self.name} ({self.prefix}) - {self.branch.name} [{self.date}]"

    def clean(self) -> None:
        super().clean()
        if self.branch_id and self.branch.organization_id != self.organization_id:
            raise ValidationError({"branch": "Branch must belong to the organization."})
        if self.branch_service_id and self.branch_service.organization_id != self.organization_id:
            raise ValidationError({"branch_service": "Service must belong to the organization."})


class QueueTicket(TimeStampedModel, PublicIdModel):
    class Status(models.TextChoices):
        WAITING = "waiting", _("Waiting in line")
        CALLED = "called", _("Called to counter")
        SERVING = "serving", _("Currently serving")
        COMPLETED = "completed", _("Service completed")
        NO_SHOW = "no_show", _("No show")
        CANCELLED = "cancelled", _("Cancelled")
        EXPIRED = "expired", _("Expired")

    class Priority(models.TextChoices):
        REGULAR = "regular", _("Regular")
        VULNERABLE = "vulnerable", _("Priority: Elderly / Pregnant / Disabled")
        EMERGENCY = "emergency", _("Priority: Immediate / Urgent Medical")

    class Source(models.TextChoices):
        ONLINE = "online", _("Online Virtual Queue")
        WALK_IN = "walk_in", _("Assisted Walk-in Registration")
        APPOINTMENT = "appointment", _("Appointment Checked-in")

    queue = models.ForeignKey(Queue, on_delete=models.PROTECT, related_name="tickets")
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="tickets")
    branch_service = models.ForeignKey(
        BranchService, on_delete=models.PROTECT, related_name="tickets"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="queue_tickets",
    )
    customer_name = models.CharField(max_length=150)
    customer_phone = models.CharField(max_length=30, blank=True)

    checklist_acknowledgement = models.ForeignKey(
        ChecklistAcknowledgement,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="tickets",
    )

    ticket_number = models.CharField(max_length=20, db_index=True)
    sequence_number = models.PositiveIntegerField(db_index=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.WAITING, db_index=True
    )
    priority = models.CharField(max_length=20, choices=Priority.choices, default=Priority.REGULAR)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.ONLINE)

    called_counter = models.ForeignKey(
        Counter, on_delete=models.SET_NULL, null=True, blank=True, related_name="tickets"
    )
    served_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="served_tickets",
    )

    joined_at = models.DateTimeField(default=timezone.now, db_index=True)
    called_at = models.DateTimeField(null=True, blank=True)
    serving_started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    recall_count = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("sequence_number",)
        indexes = [
            models.Index(fields=("queue", "status", "priority", "sequence_number")),
            models.Index(fields=("branch", "status")),
            models.Index(fields=("user", "status")),
        ]
        verbose_name = "queue ticket"
        verbose_name_plural = "queue tickets"

    def __str__(self) -> str:
        return f"{self.ticket_number} [{self.get_status_display()}] - {self.customer_name}"

    @property
    def is_active(self) -> bool:
        return self.status in {self.Status.WAITING, self.Status.CALLED, self.Status.SERVING}


class TicketEvent(TimeStampedModel):
    ticket = models.ForeignKey(QueueTicket, on_delete=models.CASCADE, related_name="events")
    action = models.CharField(max_length=50)
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    counter = models.ForeignKey(Counter, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("timestamp",)
        verbose_name = "ticket event"
        verbose_name_plural = "ticket events"

    def __str__(self) -> str:
        return f"{self.ticket.ticket_number}: {self.action} ({self.timestamp:%H:%M:%S})"
