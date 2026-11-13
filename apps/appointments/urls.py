from django.urls import path

from . import views

app_name = "appointments"

urlpatterns = [
    path("book/<uuid:branch_service_id>/", views.book_appointment_view, name="book"),
    path("<uuid:public_id>/", views.appointment_detail_view, name="detail"),
    path("<uuid:public_id>/cancel/", views.cancel_appointment_view, name="cancel"),
]
