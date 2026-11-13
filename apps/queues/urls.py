from django.urls import path

from . import views

app_name = "queues"

urlpatterns = [
    path("join/<uuid:branch_service_id>/", views.join_queue_view, name="join"),
    path("ticket/<uuid:public_id>/", views.ticket_detail_view, name="ticket_detail"),
    path("ticket/<uuid:public_id>/cancel/", views.cancel_ticket_view, name="cancel_ticket"),
]
