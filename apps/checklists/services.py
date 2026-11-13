from __future__ import annotations

from collections.abc import Iterable

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.services.models import Service

from .models import ChecklistAcknowledgement, ChecklistItem, ChecklistVersion, DocumentChecklist


@transaction.atomic
def create_checklist_version(
    checklist: DocumentChecklist,
    items: Iterable[dict],
    created_by: User | None = None,
    change_summary: str = "",
) -> ChecklistVersion:
    """Create a new immutable published version of a document checklist."""
    latest = checklist.latest_version
    next_version = (latest.version_number + 1) if latest else 1

    version = ChecklistVersion.objects.create(
        checklist=checklist,
        version_number=next_version,
        is_published=True,
        published_at=timezone.now(),
        created_by=created_by,
        change_summary=change_summary,
    )

    checklist_items = []
    for order, item_data in enumerate(items, start=1):
        checklist_items.append(
            ChecklistItem(
                version=version,
                order=order,
                title_en=item_data.get("title_en", "").strip(),
                title_fr=item_data.get("title_fr", "").strip(),
                description_en=item_data.get("description_en", "").strip(),
                description_fr=item_data.get("description_fr", "").strip(),
                is_mandatory=item_data.get("is_mandatory", True),
                condition_note_en=item_data.get("condition_note_en", "").strip(),
                condition_note_fr=item_data.get("condition_note_fr", "").strip(),
            )
        )
    ChecklistItem.objects.bulk_create(checklist_items)
    return version


def acknowledge_checklist(
    checklist_version: ChecklistVersion,
    user: User | None = None,
    ip_address: str | None = None,
    session_key: str = "",
) -> ChecklistAcknowledgement:
    """Record that a customer reviewed and confirmed having all required items."""
    return ChecklistAcknowledgement.objects.create(
        checklist_version=checklist_version,
        user=user,
        ip_address=ip_address,
        session_key=session_key,
        all_mandatory_confirmed=True,
        acknowledged_at=timezone.now(),
    )


def verify_acknowledgement_token(token: str, service: Service) -> ChecklistAcknowledgement | None:
    """Validate that the token exists, is unconsumed, and matches the service's checklist."""
    try:
        ack = ChecklistAcknowledgement.objects.select_related("checklist_version__checklist").get(
            token=token, is_consumed=False
        )
        if ack.checklist_version.checklist.service_id == service.id:
            return ack
    except (ChecklistAcknowledgement.DoesNotExist, ValueError):
        pass
    return None
