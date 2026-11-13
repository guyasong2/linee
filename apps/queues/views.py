from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.checklists.services import acknowledge_checklist
from apps.services.models import BranchService

from .engine import (
    calculate_queue_position,
    estimate_waiting_minutes,
    issue_ticket,
)
from .models import QueueTicket, TicketEvent


def join_queue_view(request: HttpRequest, branch_service_id) -> HttpResponse:
    branch_service = get_object_or_404(
        BranchService.objects.select_related("organization", "branch", "service"),
        public_id=branch_service_id,
        is_active=True,
    )

    checklist = getattr(branch_service.service, "checklist", None)
    latest_version = checklist.latest_version if checklist else None
    items = latest_version.items.all() if latest_version else []

    if request.method == "POST":
        customer_name = request.POST.get("customer_name", "").strip()
        customer_phone = request.POST.get("customer_phone", "").strip()
        priority = request.POST.get("priority", QueueTicket.Priority.REGULAR)
        acknowledged = request.POST.get("acknowledged") == "on"

        if not customer_name:
            if request.user.is_authenticated:
                customer_name = (
                    request.user.get_full_name() or request.user.phone or str(request.user)
                )
            else:
                messages.error(request, _("Please provide your full name to join the queue."))
                return render(
                    request,
                    "queues/join_queue.html",
                    {"branch_service": branch_service, "checklist": checklist, "items": items},
                )

        if items and not acknowledged:
            messages.error(
                request,
                _(
                    "You must confirm that you have all mandatory documents before joining the queue."
                ),
            )
            return render(
                request,
                "queues/join_queue.html",
                {"branch_service": branch_service, "checklist": checklist, "items": items},
            )

        # Create checklist acknowledgement record if checklist exists
        ack = None
        if latest_version:
            ack = acknowledge_checklist(
                checklist_version=latest_version,
                user=request.user if request.user.is_authenticated else None,
                ip_address=request.META.get("REMOTE_ADDR"),
                session_key=request.session.session_key or "",
            )

        try:
            ticket = issue_ticket(
                branch_service=branch_service,
                customer_name=customer_name,
                customer_phone=customer_phone
                or (getattr(request.user, "phone", "") if request.user.is_authenticated else ""),
                user=request.user if request.user.is_authenticated else None,
                acknowledgement=ack,
                priority=priority
                if priority in QueueTicket.Priority.values
                else QueueTicket.Priority.REGULAR,
                source=QueueTicket.Source.ONLINE,
            )
            messages.success(
                request, _("You have joined the queue! Your ticket is %s.") % ticket.ticket_number
            )
            return redirect("queues:ticket_detail", public_id=ticket.public_id)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))

    initial_name = request.user.get_full_name() if request.user.is_authenticated else ""
    initial_phone = request.user.phone if request.user.is_authenticated else ""

    return render(
        request,
        "queues/join_queue.html",
        {
            "branch_service": branch_service,
            "checklist": checklist,
            "items": items,
            "initial_name": initial_name,
            "initial_phone": initial_phone,
            "priorities": QueueTicket.Priority.choices,
        },
    )


def ticket_detail_view(request: HttpRequest, public_id) -> HttpResponse:
    ticket = get_object_or_404(
        QueueTicket.objects.select_related(
            "branch", "branch_service__service", "called_counter", "queue"
        ),
        public_id=public_id,
    )

    people_ahead = calculate_queue_position(ticket)
    estimated_wait = estimate_waiting_minutes(ticket)

    context = {
        "ticket": ticket,
        "people_ahead": people_ahead,
        "estimated_wait": estimated_wait,
    }

    # HTMX partial refresh for polling fallback
    if request.headers.get("HX-Request"):
        return render(request, "queues/partials/ticket_status_card.html", context)

    return render(request, "queues/ticket_detail.html", context)


@require_POST
def cancel_ticket_view(request: HttpRequest, public_id) -> HttpResponse:
    ticket = get_object_or_404(QueueTicket, public_id=public_id)

    # Only active tickets can be cancelled
    if ticket.status in [QueueTicket.Status.WAITING, QueueTicket.Status.CALLED]:
        ticket.status = QueueTicket.Status.CANCELLED
        ticket.save(update_fields=["status", "updated_at"])

        TicketEvent.objects.create(
            ticket=ticket,
            action="CANCELLED",
            actor=request.user if request.user.is_authenticated else None,
            notes="Cancelled by customer",
        )
        messages.info(request, _("Your queue ticket has been cancelled."))

    return redirect("queues:ticket_detail", public_id=ticket.public_id)
