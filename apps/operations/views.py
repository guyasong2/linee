from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from apps.accounts.permissions import membership_for
from apps.organizations.models import Branch, Counter, Organization
from apps.queues.engine import (
    call_ticket,
    complete_ticket,
    issue_ticket,
    mark_no_show,
    recall_ticket,
    start_serving,
)
from apps.queues.models import QueueTicket
from apps.services.models import BranchService


def _get_staff_branch(request: HttpRequest, organization_slug: str) -> tuple[Organization, Branch]:
    org = get_object_or_404(Organization, slug=organization_slug)
    membership = membership_for(request.user, org)
    if membership is None:
        raise Http404

    branch = membership.branch
    if not branch:
        # Organization admin can pick the first active branch
        branch = org.branches.filter(status=Branch.Status.ACTIVE).first()

    if not branch:
        raise Http404

    return org, branch


@login_required
def counter_dashboard_view(request: HttpRequest, organization_slug: str) -> HttpResponse:
    org, branch = _get_staff_branch(request, organization_slug)
    today = timezone.localdate()

    counters = branch.counters.all()
    active_counter_id = request.session.get("active_counter_id")
    active_counter = (
        counters.filter(id=active_counter_id).first() if active_counter_id else counters.first()
    )

    waiting_tickets = (
        QueueTicket.objects.filter(
            branch=branch,
            queue__date=today,
            status=QueueTicket.Status.WAITING,
        )
        .select_related("branch_service__service")
        .order_by("sequence_number")
    )

    current_ticket = None
    if active_counter:
        current_ticket = (
            QueueTicket.objects.filter(
                branch=branch,
                called_counter=active_counter,
                status__in=[QueueTicket.Status.CALLED, QueueTicket.Status.SERVING],
            )
            .select_related("branch_service__service")
            .first()
        )

    completed_today_count = QueueTicket.objects.filter(
        branch=branch, queue__date=today, status=QueueTicket.Status.COMPLETED
    ).count()

    context = {
        "organization": org,
        "branch": branch,
        "counters": counters,
        "active_counter": active_counter,
        "current_ticket": current_ticket,
        "waiting_tickets": waiting_tickets,
        "waiting_count": waiting_tickets.count(),
        "completed_count": completed_today_count,
    }

    if request.headers.get("HX-Request"):
        return render(request, "operations/partials/queue_list.html", context)

    return render(request, "operations/counter_dashboard.html", context)


@login_required
@require_POST
def select_counter_view(
    request: HttpRequest, organization_slug: str, counter_id: int
) -> HttpResponse:
    org, branch = _get_staff_branch(request, organization_slug)
    counter = get_object_or_404(Counter, id=counter_id, branch=branch)
    request.session["active_counter_id"] = counter.id
    messages.success(request, _("Operating as %s") % counter.name)
    return redirect("operations:counter_dashboard", organization_slug=org.slug)


@login_required
@require_POST
def call_next_view(request: HttpRequest, organization_slug: str) -> HttpResponse:
    org, branch = _get_staff_branch(request, organization_slug)
    active_counter_id = request.session.get("active_counter_id")
    counter = (
        branch.counters.filter(id=active_counter_id).first()
        if active_counter_id
        else branch.counters.first()
    )

    if not counter:
        messages.error(request, _("Please configure and select an active counter first."))
        return redirect("operations:counter_dashboard", organization_slug=org.slug)

    ticket = call_ticket(counter=counter, staff_user=request.user)
    if ticket:
        messages.success(
            request, _("Called ticket %s to %s") % (ticket.ticket_number, counter.name)
        )
    else:
        messages.info(request, _("No customers currently waiting in the queue."))

    return redirect("operations:counter_dashboard", organization_slug=org.slug)


@login_required
@require_POST
def recall_current_view(
    request: HttpRequest, organization_slug: str, ticket_id: int
) -> HttpResponse:
    org, branch = _get_staff_branch(request, organization_slug)
    ticket = get_object_or_404(QueueTicket, id=ticket_id, branch=branch)
    recall_ticket(ticket, request.user)
    messages.info(request, _("Recalled ticket %s") % ticket.ticket_number)
    return redirect("operations:counter_dashboard", organization_slug=org.slug)


@login_required
@require_POST
def serve_current_view(
    request: HttpRequest, organization_slug: str, ticket_id: int
) -> HttpResponse:
    org, branch = _get_staff_branch(request, organization_slug)
    ticket = get_object_or_404(QueueTicket, id=ticket_id, branch=branch)
    start_serving(ticket, request.user)
    messages.success(request, _("Now serving ticket %s") % ticket.ticket_number)
    return redirect("operations:counter_dashboard", organization_slug=org.slug)


@login_required
@require_POST
def complete_current_view(
    request: HttpRequest, organization_slug: str, ticket_id: int
) -> HttpResponse:
    org, branch = _get_staff_branch(request, organization_slug)
    ticket = get_object_or_404(QueueTicket, id=ticket_id, branch=branch)
    notes = request.POST.get("notes", "").strip()
    complete_ticket(ticket, request.user, notes=notes)
    messages.success(request, _("Completed ticket %s") % ticket.ticket_number)
    return redirect("operations:counter_dashboard", organization_slug=org.slug)


@login_required
@require_POST
def no_show_current_view(
    request: HttpRequest, organization_slug: str, ticket_id: int
) -> HttpResponse:
    org, branch = _get_staff_branch(request, organization_slug)
    ticket = get_object_or_404(QueueTicket, id=ticket_id, branch=branch)
    mark_no_show(ticket, request.user)
    messages.warning(request, _("Marked ticket %s as No-Show") % ticket.ticket_number)
    return redirect("operations:counter_dashboard", organization_slug=org.slug)


# ── Front-desk assisted registration (<1 min walk-in flow) ───────────


@login_required
def assisted_registration_view(request: HttpRequest, organization_slug: str) -> HttpResponse:
    org, branch = _get_staff_branch(request, organization_slug)
    branch_services = branch.branch_services.filter(is_active=True).select_related("service")

    if request.method == "POST":
        service_id = request.POST.get("branch_service_id")
        customer_name = request.POST.get("customer_name", "").strip()
        customer_phone = request.POST.get("customer_phone", "").strip()
        priority = request.POST.get("priority", QueueTicket.Priority.REGULAR)

        if not service_id or not customer_name:
            messages.error(request, _("Please provide customer name and select a service."))
        else:
            branch_service = get_object_or_404(BranchService, id=service_id, branch=branch)
            ticket = issue_ticket(
                branch_service=branch_service,
                customer_name=customer_name,
                customer_phone=customer_phone,
                priority=priority
                if priority in QueueTicket.Priority.values
                else QueueTicket.Priority.REGULAR,
                source=QueueTicket.Source.WALK_IN,
            )
            messages.success(
                request,
                _("Issued walk-in ticket %s for %s") % (ticket.ticket_number, customer_name),
            )
            return redirect("queues:ticket_detail", public_id=ticket.public_id)

    return render(
        request,
        "operations/assisted_registration.html",
        {
            "organization": org,
            "branch": branch,
            "branch_services": branch_services,
            "priorities": QueueTicket.Priority.choices,
        },
    )


# ── Public Display Board (TV Screen Interface) ───────────────────────


def public_display_board_view(request: HttpRequest, branch_id) -> HttpResponse:
    branch = get_object_or_404(Branch.objects.select_related("organization"), public_id=branch_id)
    today = timezone.localdate()

    # Get the 8 most recently called/serving tickets (strictly privacy safe: NO full names/phones)
    active_announcements = (
        QueueTicket.objects.filter(
            branch=branch,
            queue__date=today,
            status__in=[QueueTicket.Status.CALLED, QueueTicket.Status.SERVING],
        )
        .select_related("called_counter", "branch_service__service")
        .order_by("-called_at")[:8]
    )

    waiting_count = QueueTicket.objects.filter(
        branch=branch, queue__date=today, status=QueueTicket.Status.WAITING
    ).count()

    context = {
        "branch": branch,
        "active_announcements": active_announcements,
        "waiting_count": waiting_count,
        "now": timezone.now(),
    }

    if request.headers.get("HX-Request"):
        return render(request, "operations/partials/display_board_content.html", context)

    return render(request, "operations/public_display_board.html", context)
