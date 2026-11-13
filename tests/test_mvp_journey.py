from __future__ import annotations

import datetime

import pytest
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.appointments.models import Appointment, AppointmentSlot
from apps.appointments.services import book_appointment
from apps.checklists.models import ChecklistItem, ChecklistVersion, DocumentChecklist
from apps.checklists.services import acknowledge_checklist
from apps.organizations.models import Branch, Counter, Organization, OrganizationMembership
from apps.queues.engine import (
    call_ticket,
    complete_ticket,
    issue_ticket,
    recall_ticket,
    start_serving,
)
from apps.queues.models import QueueTicket
from apps.services.models import BranchService, Service, ServiceFee


@pytest.fixture
def test_setup(db):
    org = Organization.objects.create(
        name="Test Douala Clinic",
        slug="test-douala-clinic",
        organization_type=Organization.Type.CLINIC,
        status=Organization.Status.ACTIVE,
        city="Douala",
    )
    branch = Branch.objects.create(
        organization=org,
        name="Main Branch",
        code="MB",
        status=Branch.Status.ACTIVE,
        city="Douala",
    )
    counter1 = Counter.objects.create(
        organization=org,
        branch=branch,
        name="Counter 1",
        code="C1",
        status=Counter.Status.OPEN,
    )
    service = Service.objects.create(
        organization=org,
        code="MED",
        name_en="Medical Consultation",
        name_fr="Consultation Médicale",
        category=Service.Category.CONSULTATION,
        is_active=True,
    )
    branch_service = BranchService.objects.create(
        organization=org,
        branch=branch,
        service=service,
        default_duration_minutes=20,
        is_active=True,
    )
    ServiceFee.objects.create(
        organization=org,
        branch_service=branch_service,
        amount_xaf=5000,
        is_active=True,
        published_at=timezone.now(),
    )
    checklist = DocumentChecklist.objects.create(
        organization=org,
        service=service,
        title_en="Required Consultation Documents",
        is_active=True,
    )
    version = ChecklistVersion.objects.create(
        checklist=checklist,
        version_number=1,
        is_published=True,
    )
    ChecklistItem.objects.create(
        version=version,
        order=1,
        title_en="National ID Card",
        is_mandatory=True,
    )
    user = User.objects.create_user(
        phone="+237677000111",
        email="patient@example.com",
        password="ValidPassword123#",
        full_name="Jean Patient",
    )
    staff = User.objects.create_user(
        phone="+237677999888",
        email="staff@example.com",
        password="ValidPassword123#",
        full_name="Dr. Staff",
    )
    OrganizationMembership.objects.create(
        organization=org,
        branch=branch,
        user=staff,
        role=OrganizationMembership.Role.COUNTER_STAFF,
        is_active=True,
    )
    return {
        "org": org,
        "branch": branch,
        "counter": counter1,
        "service": service,
        "branch_service": branch_service,
        "checklist": checklist,
        "version": version,
        "user": user,
        "staff": staff,
    }


def test_checklist_acknowledgement_required_for_booking(test_setup):
    """Booking without checklist acknowledgement must fail."""
    bs = test_setup["branch_service"]
    user = test_setup["user"]
    slot = AppointmentSlot.objects.create(
        branch_service=bs,
        date=timezone.localdate() + datetime.timedelta(days=1),
        start_time=datetime.time(9, 0),
        end_time=datetime.time(9, 20),
        capacity=1,
        booked_count=0,
    )

    with pytest.raises(ValidationError):
        book_appointment(
            branch_service=bs,
            slot_id=slot.id,
            customer_name="Jean Patient",
            user=user,
            acknowledgement=None,  # Missing!
        )


def test_appointment_booking_with_acknowledgement_and_capacity(test_setup):
    """Booking with valid acknowledgement succeeds and enforces capacity."""
    bs = test_setup["branch_service"]
    user = test_setup["user"]
    version = test_setup["version"]

    ack = acknowledge_checklist(checklist_version=version, user=user)
    slot = AppointmentSlot.objects.create(
        branch_service=bs,
        date=timezone.localdate() + datetime.timedelta(days=1),
        start_time=datetime.time(10, 0),
        end_time=datetime.time(10, 20),
        capacity=1,
        booked_count=0,
    )

    appt = book_appointment(
        branch_service=bs,
        slot_id=slot.id,
        customer_name="Jean Patient",
        customer_phone="+237677000111",
        user=user,
        acknowledgement=ack,
    )
    assert appt.reference.startswith("APT-")
    assert appt.status == Appointment.Status.CONFIRMED

    slot.refresh_from_db()
    assert slot.booked_count == 1
    assert slot.has_availability is False

    # Second booking must fail due to zero capacity
    ack2 = acknowledge_checklist(checklist_version=version, user=user)
    with pytest.raises(ValidationError):
        book_appointment(
            branch_service=bs,
            slot_id=slot.id,
            customer_name="Second Person",
            user=user,
            acknowledgement=ack2,
        )


def test_queue_atomic_ticket_generation_and_duplicate_prevention(test_setup):
    """Queue generates sequential tickets and blocks duplicate active tickets."""
    bs = test_setup["branch_service"]
    user = test_setup["user"]

    t1 = issue_ticket(
        branch_service=bs,
        customer_name="Jean Patient",
        customer_phone="+237677000111",
        user=user,
    )
    assert t1.ticket_number == "M-001"
    assert t1.sequence_number == 1
    assert t1.status == QueueTicket.Status.WAITING

    # Attempting to issue another ticket while active must fail
    with pytest.raises(ValidationError):
        issue_ticket(
            branch_service=bs,
            customer_name="Jean Patient",
            user=user,
        )

    # Different walk-in customer gets next sequence number M-002
    t2 = issue_ticket(
        branch_service=bs,
        customer_name="Marie Walk-in",
        user=None,
    )
    assert t2.ticket_number == "M-002"
    assert t2.sequence_number == 2


def test_queue_priority_ordering(test_setup):
    """Emergency and vulnerable tickets are called ahead of earlier regular tickets."""
    bs = test_setup["branch_service"]
    counter = test_setup["counter"]
    staff = test_setup["staff"]

    # Ticket 1: Regular
    issue_ticket(
        branch_service=bs,
        customer_name="Regular Customer",
        priority=QueueTicket.Priority.REGULAR,
    )
    # Ticket 2: Emergency (arrived later)
    t_emergency = issue_ticket(
        branch_service=bs,
        customer_name="Urgent Patient",
        priority=QueueTicket.Priority.EMERGENCY,
    )

    # Calling next should pick Emergency first despite higher sequence number
    called = call_ticket(counter=counter, staff_user=staff)
    assert called.id == t_emergency.id
    assert called.status == QueueTicket.Status.CALLED
    assert called.called_counter == counter


def test_queue_lifecycle_transitions(test_setup):
    """Full ticket journey: WAITING -> CALLED -> SERVING -> COMPLETED."""
    bs = test_setup["branch_service"]
    counter = test_setup["counter"]
    staff = test_setup["staff"]

    ticket = issue_ticket(
        branch_service=bs,
        customer_name="Test Citizen",
        priority=QueueTicket.Priority.REGULAR,
    )
    assert ticket.status == QueueTicket.Status.WAITING

    called = call_ticket(counter=counter, staff_user=staff, ticket_id=ticket.id)
    assert called.status == QueueTicket.Status.CALLED

    # Recall ticket
    recalled = recall_ticket(called, staff_user=staff)
    assert recalled.recall_count == 1

    # Start serving
    serving = start_serving(recalled, staff_user=staff)
    assert serving.status == QueueTicket.Status.SERVING
    assert serving.serving_started_at is not None

    # Complete ticket
    done = complete_ticket(serving, staff_user=staff, notes="All finished.")
    assert done.status == QueueTicket.Status.COMPLETED
    assert done.completed_at is not None


def test_public_display_board_privacy(test_setup):
    """Public display board renders HTTP 200 and never exposes customer phone numbers."""
    client = Client()
    branch = test_setup["branch"]
    bs = test_setup["branch_service"]
    counter = test_setup["counter"]
    staff = test_setup["staff"]

    ticket = issue_ticket(
        branch_service=bs,
        customer_name="Secret Name",
        customer_phone="+237699887766",
    )
    call_ticket(counter=counter, staff_user=staff, ticket_id=ticket.id)

    url = reverse("operations:display_board", kwargs={"branch_id": branch.public_id})
    response = client.get(url)
    assert response.status_code == 200

    content = response.content.decode("utf-8")
    assert ticket.ticket_number in content
    # Customer phone number must NEVER be on public display
    assert "+237699887766" not in content
