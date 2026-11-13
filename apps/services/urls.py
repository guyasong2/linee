from django.urls import path

from . import views

app_name = "services"

urlpatterns = [
    path("", views.service_search, name="search"),
    path("<uuid:public_id>/", views.service_detail, name="detail"),
]
