from __future__ import annotations

import datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext as _

from apps.accounts.models import User
from apps.checklists.models import ChecklistAcknowledgement
from apps.services.models import BranchService

from .models import Appointment, AppointmentSlot, generate_appointment_reference


@transaction.atomic
def generate_slots_for_day(
    branch_service: BranchService,
    target_date: datetime.date,
    start_hour: int = 8,
    end_hour: int = 16,
    duration_minutes: int | None = None,
    capacity_per_slot: int = 2,
) -> list[AppointmentSlot]:
    """Generate discrete appointment booking windows for a service on a given date."""
    if duration_minutes is None:
        duration_minutes = branch_service.default_duration_minutes or 20

    current_time = datetime.time(start_hour, 0)
    end_time_limit = datetime.time(end_hour, 0)

    created_slots = []
    while current_time < end_time_limit:
        dt_start = datetime.datetime.combine(target_date, current_time)
        dt_end = dt_start + datetime.timedelta(minutes=duration_minutes)
        if dt_end.time() > end_time_limit:
            break

        slot, _ = AppointmentSlot.objects.get_or_create(
            branch_service=branch_service,
            date=target_date,
            start_time=current_time,
            defaults={
                "end_time": dt_end.time(),
                "capacity": capacity_per_slot,
                "booked_count": 0,
                "is_active": True,
            },
        )
        created_slots.append(slot)
        current_time = dt_end.time()

    return created_slots


@transaction.atomic
def book_appointment(
    branch_service: BranchService,
    slot_id: int,
    customer_name: str,
    customer_phone: str = "",
    customer_email: str = "",
    user: User | None = None,
    acknowledgement: ChecklistAcknowledgement | None = None,
    notes: str = "",
) -> Appointment:
    """
    Reserve an appointment slot with atomic capacity enforcement.
    Requires checklist acknowledgement validation.
    """
    if acknowledgement is None:
        raise ValidationError(
            _("You must review and acknowledge the document checklist before booking.")
        )

    if acknowledgement.is_consumed:
        raise ValidationError(_("This checklist verification token has already been used."))

    slot = AppointmentSlot.objects.select_for_update().get(
        id=slot_id, branch_service=branch_service, is_active=True
    )

    if slot.booked_count >= slot.capacity:
        raise ValidationError(
            _("This appointment time is now fully booked. Please choose another time.")
        )

    # Increment slot booked count
    slot.booked_count += 1
    slot.save(update_fields=["booked_count", "updated_at"])

    # Mark acknowledgement as consumed
    acknowledgement.is_consumed = True
    acknowledgement.save(update_fields=["is_consumed"])

    appointment = Appointment.objects.create(
        reference=generate_appointment_reference(),
        organization=branch_service.organization,
        branch=branch_service.branch,
        branch_service=branch_service,
        slot=slot,
        user=user,
        customer_name=customer_name.strip(),
        customer_phone=customer_phone.strip(),
        customer_email=customer_email.strip(),
        checklist_acknowledgement=acknowledgement,
        appointment_date=slot.date,
        scheduled_time=slot.start_time,
        status=Appointment.Status.CONFIRMED,
        notes=notes.strip(),
    )

    return appointment
