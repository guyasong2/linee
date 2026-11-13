from django.urls import path

from . import views

app_name = "organizations"

urlpatterns = [
    path("<slug:organization_slug>/", views.dashboard, name="dashboard"),
]
