from django.urls import path

from . import views

app_name = "operations"

urlpatterns = [
    path(
        "<slug:organization_slug>/counter/", views.counter_dashboard_view, name="counter_dashboard"
    ),
    path(
        "<slug:organization_slug>/counter/select/<int:counter_id>/",
        views.select_counter_view,
        name="select_counter",
    ),
    path("<slug:organization_slug>/counter/call-next/", views.call_next_view, name="call_next"),
    path(
        "<slug:organization_slug>/counter/recall/<int:ticket_id>/",
        views.recall_current_view,
        name="recall",
    ),
    path(
        "<slug:organization_slug>/counter/serve/<int:ticket_id>/",
        views.serve_current_view,
        name="serve",
    ),
    path(
        "<slug:organization_slug>/counter/complete/<int:ticket_id>/",
        views.complete_current_view,
        name="complete",
    ),
    path(
        "<slug:organization_slug>/counter/no-show/<int:ticket_id>/",
        views.no_show_current_view,
        name="no_show",
    ),
    path("<slug:organization_slug>/walk-in/", views.assisted_registration_view, name="walk_in"),
    path("display/<uuid:branch_id>/", views.public_display_board_view, name="display_board"),
]
