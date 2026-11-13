from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import get_language

from apps.common.models import PublicIdModel, TimeStampedModel
from apps.organizations.models import Organization
from apps.services.models import Service


class DocumentChecklist(TimeStampedModel, PublicIdModel):
    organization = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="document_checklists"
    )
    service = models.OneToOneField(Service, on_delete=models.CASCADE, related_name="checklist")
    title_en = models.CharField(max_length=200, default="Required Documents & Preparation")
    title_fr = models.CharField(max_length=200, default="Documents requis et préparation")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("service__name_en",)
        verbose_name = "document checklist"
        verbose_name_plural = "document checklists"

    def __str__(self) -> str:
        return f"Checklist: {self.service.name_en} ({self.organization.name})"

    @property
    def display_title(self) -> str:
        if (get_language() or "").startswith("fr") and self.title_fr:
            return self.title_fr
        return self.title_en

    @property
    def latest_version(self) -> ChecklistVersion | None:
        return self.versions.filter(is_published=True).order_by("-version_number").first()

    def clean(self) -> None:
        super().clean()
        if self.service_id and self.service.organization_id != self.organization_id:
            raise ValidationError({"service": "The service must belong to the same organization."})


class ChecklistVersion(TimeStampedModel, PublicIdModel):
    checklist = models.ForeignKey(
        DocumentChecklist, on_delete=models.CASCADE, related_name="versions"
    )
    version_number = models.PositiveIntegerField(default=1)
    is_published = models.BooleanField(default=True)
    published_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_checklist_versions",
    )
    change_summary = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("-version_number",)
        constraints = [
            models.UniqueConstraint(
                fields=("checklist", "version_number"),
                name="unique_checklist_version_number",
            )
        ]
        verbose_name = "checklist version"
        verbose_name_plural = "checklist versions"

    def __str__(self) -> str:
        return f"{self.checklist} v{self.version_number}"


class ChecklistItem(TimeStampedModel):
    version = models.ForeignKey(ChecklistVersion, on_delete=models.CASCADE, related_name="items")
    order = models.PositiveIntegerField(default=1)
    title_en = models.CharField(max_length=250)
    title_fr = models.CharField(max_length=250, blank=True)
    description_en = models.TextField(blank=True)
    description_fr = models.TextField(blank=True)
    is_mandatory = models.BooleanField(
        default=True, help_text="Customer cannot proceed without having this item."
    )
    condition_note_en = models.CharField(
        max_length=250,
        blank=True,
        help_text="e.g. 'Only required if accompanied by minors' or 'Original + 2 copies'",
    )
    condition_note_fr = models.CharField(
        max_length=250,
        blank=True,
        help_text="e.g. 'Requis uniquement en cas de mineur' ou 'Original + 2 copies'",
    )

    class Meta:
        ordering = ("order", "id")
        verbose_name = "checklist item"
        verbose_name_plural = "checklist items"

    def __str__(self) -> str:
        return f"{self.order}. {self.title_en} ({'Mandatory' if self.is_mandatory else 'Optional'})"

    @property
    def display_title(self) -> str:
        if (get_language() or "").startswith("fr") and self.title_fr:
            return self.title_fr
        return self.title_en

    @property
    def display_description(self) -> str:
        if (get_language() or "").startswith("fr") and self.description_fr:
            return self.description_fr
        return self.description_en

    @property
    def display_condition(self) -> str:
        if (get_language() or "").startswith("fr") and self.condition_note_fr:
            return self.condition_note_fr
        return self.condition_note_en


class ChecklistAcknowledgement(TimeStampedModel):
    """
    Cryptographic/UUID token proving that the customer confirmed they reviewed
    and possess all required documents prior to booking or joining the virtual queue.
    """

    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)
    checklist_version = models.ForeignKey(
        ChecklistVersion, on_delete=models.PROTECT, related_name="acknowledgements"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checklist_acknowledgements",
    )
    acknowledged_at = models.DateTimeField(default=timezone.now)
    all_mandatory_confirmed = models.BooleanField(default=True)
    session_key = models.CharField(max_length=64, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    is_consumed = models.BooleanField(
        default=False, help_text="Marked True when attached to an appointment or ticket."
    )

    class Meta:
        ordering = ("-acknowledged_at",)
        verbose_name = "checklist acknowledgement"
        verbose_name_plural = "checklist acknowledgements"

    def __str__(self) -> str:
        return f"Ack {self.token} for {self.checklist_version}"
