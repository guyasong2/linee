from __future__ import annotations

import datetime

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.checklists.services import acknowledge_checklist
from apps.services.models import BranchService

from .models import Appointment, AppointmentSlot
from .services import book_appointment, generate_slots_for_day


def book_appointment_view(request: HttpRequest, branch_service_id) -> HttpResponse:
    branch_service = get_object_or_404(
        BranchService.objects.select_related("organization", "branch", "service"),
        public_id=branch_service_id,
        is_active=True,
    )

    checklist = getattr(branch_service.service, "checklist", None)
    latest_version = checklist.latest_version if checklist else None
    checklist_items = latest_version.items.all() if latest_version else []

    today = timezone.localdate()
    # Ensure next 7 days have available appointment slots
    for day_offset in range(1, 8):
        target_date = today + datetime.timedelta(days=day_offset)
        # Skip Sundays
        if target_date.weekday() != 6:
            existing_count = AppointmentSlot.objects.filter(
                branch_service=branch_service, date=target_date
            ).count()
            if existing_count == 0:
                generate_slots_for_day(branch_service, target_date)

    available_slots = AppointmentSlot.objects.filter(
        branch_service=branch_service,
        date__gte=today + datetime.timedelta(days=1),
        date__lte=today + datetime.timedelta(days=14),
        is_active=True,
    ).order_by("date", "start_time")

    # Filter only slots with remaining capacity
    slots_with_capacity = [s for s in available_slots if s.has_availability]

    if request.method == "POST":
        customer_name = request.POST.get("customer_name", "").strip()
        customer_phone = request.POST.get("customer_phone", "").strip()
        customer_email = request.POST.get("customer_email", "").strip()
        slot_id = request.POST.get("slot_id")
        acknowledged = request.POST.get("acknowledged") == "on"

        if not customer_name:
            if request.user.is_authenticated:
                customer_name = (
                    request.user.get_full_name() or request.user.phone or str(request.user)
                )
            else:
                messages.error(request, _("Please provide your name."))
                return render(
                    request,
                    "appointments/book.html",
                    {
                        "branch_service": branch_service,
                        "checklist_items": checklist_items,
                        "slots": slots_with_capacity,
                    },
                )

        if not slot_id:
            messages.error(request, _("Please select an available appointment slot."))
            return render(
                request,
                "appointments/book.html",
                {
                    "branch_service": branch_service,
                    "checklist_items": checklist_items,
                    "slots": slots_with_capacity,
                },
            )

        if checklist_items and not acknowledged:
            messages.error(
                request, _("You must confirm that you have all mandatory documents before booking.")
            )
            return render(
                request,
                "appointments/book.html",
                {
                    "branch_service": branch_service,
                    "checklist_items": checklist_items,
                    "slots": slots_with_capacity,
                },
            )

        ack = None
        if latest_version:
            ack = acknowledge_checklist(
                checklist_version=latest_version,
                user=request.user if request.user.is_authenticated else None,
                ip_address=request.META.get("REMOTE_ADDR"),
                session_key=request.session.session_key or "",
            )

        try:
            appointment = book_appointment(
                branch_service=branch_service,
                slot_id=int(slot_id),
                customer_name=customer_name,
                customer_phone=customer_phone
                or (getattr(request.user, "phone", "") if request.user.is_authenticated else ""),
                customer_email=customer_email
                or (getattr(request.user, "email", "") if request.user.is_authenticated else ""),
                user=request.user if request.user.is_authenticated else None,
                acknowledgement=ack,
            )
            messages.success(
                request, _("Appointment booked successfully! Reference: %s") % appointment.reference
            )
            return redirect("appointments:detail", public_id=appointment.public_id)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))

    initial_name = request.user.get_full_name() if request.user.is_authenticated else ""
    initial_phone = request.user.phone if request.user.is_authenticated else ""
    initial_email = request.user.email if request.user.is_authenticated else ""

    return render(
        request,
        "appointments/book.html",
        {
            "branch_service": branch_service,
            "checklist": checklist,
            "checklist_items": checklist_items,
            "slots": slots_with_capacity,
            "initial_name": initial_name,
            "initial_phone": initial_phone,
            "initial_email": initial_email,
        },
    )


def appointment_detail_view(request: HttpRequest, public_id) -> HttpResponse:
    appointment = get_object_or_404(
        Appointment.objects.select_related(
            "branch", "branch_service__service", "organization", "slot"
        ),
        public_id=public_id,
    )
    return render(
        request,
        "appointments/detail.html",
        {"appointment": appointment},
    )


@require_POST
def cancel_appointment_view(request: HttpRequest, public_id) -> HttpResponse:
    appointment = get_object_or_404(Appointment, public_id=public_id)

    if appointment.status == Appointment.Status.CONFIRMED:
        appointment.status = Appointment.Status.CANCELLED
        appointment.cancelled_at = timezone.now()
        appointment.cancellation_reason = "Cancelled by customer"
        appointment.save(
            update_fields=["status", "cancelled_at", "cancellation_reason", "updated_at"]
        )

        # Release capacity on slot
        if appointment.slot and appointment.slot.booked_count > 0:
            appointment.slot.booked_count -= 1
            appointment.slot.save(update_fields=["booked_count", "updated_at"])

        messages.info(request, _("Your appointment has been cancelled."))

    return redirect("appointments:detail", public_id=appointment.public_id)
