from __future__ import annotations

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext as _

from apps.accounts.models import User
from apps.checklists.models import ChecklistAcknowledgement
from apps.organizations.models import Counter
from apps.services.models import BranchService

from .models import Queue, QueueTicket, TicketEvent

logger = logging.getLogger(__name__)


def broadcast_queue_update(group_name: str, event_type: str, data: dict):
    """Safely broadcast an event to a Channels group (silently fails if channel layer unavailable)."""
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                group_name,
                {
                    "type": "queue.message",
                    "event": event_type,
                    "data": data,
                },
            )
    except Exception as exc:
        logger.warning(f"Could not broadcast queue message to group {group_name}: {exc}")


@transaction.atomic
def get_or_create_daily_queue(branch_service: BranchService, date=None) -> Queue:
    """Find or create today's queue for a given branch service."""
    if date is None:
        date = timezone.localdate()

    prefix = (branch_service.service.code[:1] or "A").upper()
    queue = (
        Queue.objects.select_for_update()
        .filter(branch=branch_service.branch, prefix=prefix, date=date)
        .first()
    )
    if queue is None:
        queue = Queue.objects.create(
            organization=branch_service.organization,
            branch=branch_service.branch,
            branch_service=branch_service,
            name=f"{branch_service.service.name_en} Queue",
            prefix=prefix,
            date=date,
            max_daily_capacity=150,
            current_sequence=0,
        )
    return queue


@transaction.atomic
def issue_ticket(
    branch_service: BranchService,
    customer_name: str,
    customer_phone: str = "",
    user: User | None = None,
    acknowledgement: ChecklistAcknowledgement | None = None,
    priority: str = QueueTicket.Priority.REGULAR,
    source: str = QueueTicket.Source.ONLINE,
) -> QueueTicket:
    """
    Generate an atomic, sequential ticket for a customer in today's virtual queue.
    Guarantees concurrency safety using select_for_update on the Queue instance.
    """
    today = timezone.localdate()
    queue = get_or_create_daily_queue(branch_service, date=today)

    if queue.is_paused:
        raise ValidationError(_("This queue is temporarily paused by the facility."))

    if queue.current_sequence >= queue.max_daily_capacity:
        raise ValidationError(_("Today's maximum capacity for this queue has been reached."))

    # Prevent active duplicate tickets for the same authenticated user in the same queue
    if (
        user
        and QueueTicket.objects.filter(
            queue=queue,
            user=user,
            status__in=[
                QueueTicket.Status.WAITING,
                QueueTicket.Status.CALLED,
                QueueTicket.Status.SERVING,
            ],
        ).exists()
    ):
        raise ValidationError(_("You already have an active ticket in this queue."))

    # Increment sequence safely
    queue.current_sequence += 1
    queue.save(update_fields=["current_sequence", "updated_at"])

    ticket_number = f"{queue.prefix}-{str(queue.current_sequence).zfill(3)}"

    ticket = QueueTicket.objects.create(
        queue=queue,
        branch=branch_service.branch,
        branch_service=branch_service,
        user=user,
        customer_name=customer_name.strip(),
        customer_phone=customer_phone.strip(),
        checklist_acknowledgement=acknowledgement,
        ticket_number=ticket_number,
        sequence_number=queue.current_sequence,
        priority=priority,
        source=source,
        status=QueueTicket.Status.WAITING,
        joined_at=timezone.now(),
    )

    if acknowledgement:
        acknowledgement.is_consumed = True
        acknowledgement.save(update_fields=["is_consumed"])

    TicketEvent.objects.create(
        ticket=ticket,
        action="JOINED",
        to_status=QueueTicket.Status.WAITING,
        actor=user,
        notes=f"Issued ticket {ticket_number} via {source}",
    )

    # Broadcast to branch display board & ticket channel
    broadcast_queue_update(
        f"branch_{branch_service.branch.public_id}",
        "ticket_joined",
        {
            "ticket_number": ticket.ticket_number,
            "status": ticket.status,
            "service_name": branch_service.display_name,
        },
    )

    return ticket


@transaction.atomic
def call_ticket(
    counter: Counter, staff_user: User, ticket_id: int | None = None
) -> QueueTicket | None:
    """
    Call the next eligible ticket (or a specific ticket) to a counter.
    Sorts by: Emergency > Vulnerable > Regular, then sequence_number ascending.
    """
    queryset = QueueTicket.objects.select_for_update().filter(
        branch=counter.branch, status=QueueTicket.Status.WAITING
    )

    if ticket_id:
        ticket = queryset.filter(id=ticket_id).first()
    else:
        # Priority ordering: Emergency first, then Vulnerable, then Regular
        ticket = queryset.order_by(
            models.Case(
                models.When(priority=QueueTicket.Priority.EMERGENCY, then=models.Value(1)),
                models.When(priority=QueueTicket.Priority.VULNERABLE, then=models.Value(2)),
                default=models.Value(3),
                output_field=models.IntegerField(),
            ),
            "sequence_number",
        ).first()

    if not ticket:
        return None

    previous_status = ticket.status
    ticket.status = QueueTicket.Status.CALLED
    ticket.called_counter = counter
    ticket.called_at = timezone.now()
    ticket.served_by = staff_user
    ticket.save(update_fields=["status", "called_counter", "called_at", "served_by", "updated_at"])

    TicketEvent.objects.create(
        ticket=ticket,
        action="CALLED",
        from_status=previous_status,
        to_status=QueueTicket.Status.CALLED,
        actor=staff_user,
        counter=counter,
        notes=f"Called to {counter.name}",
    )

    # Update counter status
    counter.status = Counter.Status.OPEN
    counter.current_staff = staff_user
    counter.save(update_fields=["status", "current_staff", "updated_at"])

    # Broadcast to public display & customer
    broadcast_payload = {
        "ticket_number": ticket.ticket_number,
        "counter_name": counter.name,
        "counter_code": counter.code,
        "service_name": ticket.branch_service.display_name,
        "status": ticket.status,
    }
    broadcast_queue_update(f"branch_{counter.branch.public_id}", "ticket_called", broadcast_payload)
    broadcast_queue_update(f"ticket_{ticket.public_id}", "ticket_called", broadcast_payload)

    return ticket


@transaction.atomic
def recall_ticket(ticket: QueueTicket, staff_user: User) -> QueueTicket:
    """Re-announce an already called ticket that hasn't appeared yet."""
    ticket.recall_count += 1
    ticket.called_at = timezone.now()
    ticket.save(update_fields=["recall_count", "called_at", "updated_at"])

    TicketEvent.objects.create(
        ticket=ticket,
        action="RECALLED",
        actor=staff_user,
        counter=ticket.called_counter,
        notes=f"Recalled (Count: {ticket.recall_count})",
    )

    if ticket.called_counter:
        payload = {
            "ticket_number": ticket.ticket_number,
            "counter_name": ticket.called_counter.name,
            "counter_code": ticket.called_counter.code,
            "recall_count": ticket.recall_count,
        }
        broadcast_queue_update(f"branch_{ticket.branch.public_id}", "ticket_recalled", payload)
        broadcast_queue_update(f"ticket_{ticket.public_id}", "ticket_recalled", payload)

    return ticket


@transaction.atomic
def start_serving(ticket: QueueTicket, staff_user: User) -> QueueTicket:
    """Mark that the customer has arrived at the counter and service has begun."""
    previous_status = ticket.status
    ticket.status = QueueTicket.Status.SERVING
    ticket.serving_started_at = timezone.now()
    ticket.served_by = staff_user
    ticket.save(update_fields=["status", "serving_started_at", "served_by", "updated_at"])

    TicketEvent.objects.create(
        ticket=ticket,
        action="SERVING",
        from_status=previous_status,
        to_status=QueueTicket.Status.SERVING,
        actor=staff_user,
        counter=ticket.called_counter,
    )

    broadcast_queue_update(
        f"ticket_{ticket.public_id}",
        "ticket_serving",
        {"ticket_number": ticket.ticket_number, "status": ticket.status},
    )
    return ticket


@transaction.atomic
def complete_ticket(ticket: QueueTicket, staff_user: User, notes: str = "") -> QueueTicket:
    """Mark service as successfully completed."""
    previous_status = ticket.status
    ticket.status = QueueTicket.Status.COMPLETED
    ticket.completed_at = timezone.now()
    if notes:
        ticket.notes = notes
    ticket.save(update_fields=["status", "completed_at", "notes", "updated_at"])

    TicketEvent.objects.create(
        ticket=ticket,
        action="COMPLETED",
        from_status=previous_status,
        to_status=QueueTicket.Status.COMPLETED,
        actor=staff_user,
        counter=ticket.called_counter,
        notes=notes,
    )

    payload = {"ticket_number": ticket.ticket_number, "status": ticket.status}
    broadcast_queue_update(f"branch_{ticket.branch.public_id}", "ticket_completed", payload)
    broadcast_queue_update(f"ticket_{ticket.public_id}", "ticket_completed", payload)

    return ticket


@transaction.atomic
def mark_no_show(ticket: QueueTicket, staff_user: User) -> QueueTicket:
    """Mark ticket as no-show when customer fails to appear."""
    previous_status = ticket.status
    ticket.status = QueueTicket.Status.NO_SHOW
    ticket.save(update_fields=["status", "updated_at"])

    TicketEvent.objects.create(
        ticket=ticket,
        action="NO_SHOW",
        from_status=previous_status,
        to_status=QueueTicket.Status.NO_SHOW,
        actor=staff_user,
        counter=ticket.called_counter,
    )

    payload = {"ticket_number": ticket.ticket_number, "status": ticket.status}
    broadcast_queue_update(f"branch_{ticket.branch.public_id}", "ticket_no_show", payload)
    broadcast_queue_update(f"ticket_{ticket.public_id}", "ticket_no_show", payload)

    return ticket


def calculate_queue_position(ticket: QueueTicket) -> int:
    """Calculate how many people are waiting ahead of this ticket in line."""
    if ticket.status != QueueTicket.Status.WAITING:
        return 0

    return QueueTicket.objects.filter(
        queue=ticket.queue,
        status=QueueTicket.Status.WAITING,
        sequence_number__lt=ticket.sequence_number,
    ).count()


def estimate_waiting_minutes(ticket: QueueTicket) -> int:
    """
    Estimate wait time in minutes based on:
    - People ahead
    - Average service duration
    - Active counters currently serving
    """
    position = calculate_queue_position(ticket)
    avg_duration = ticket.branch_service.default_duration_minutes or 15

    active_counters = (
        Counter.objects.filter(
            branch=ticket.branch,
            status__in=[Counter.Status.OPEN, Counter.Status.PAUSED],
        ).count()
        or 1
    )

    estimated_minutes = (position * avg_duration) // active_counters
    return max(5, estimated_minutes) if position > 0 else 0
