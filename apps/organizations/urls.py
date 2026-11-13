from django.urls import path

from . import views

app_name = "organizations"

urlpatterns = [
    path("<slug:organization_slug>/", views.dashboard, name="dashboard"),
    path("<slug:organization_slug>/edit/", views.edit_organization, name="edit"),
    path("<slug:organization_slug>/branches/", views.branch_list, name="branches"),
    path("<slug:organization_slug>/branches/add/", views.branch_add, name="branch_add"),
    path(
        "<slug:organization_slug>/branches/<int:pk>/edit/",
        views.branch_edit,
        name="branch_edit",
    ),
    path("<slug:organization_slug>/services/", views.service_list, name="services"),
    path("<slug:organization_slug>/services/add/", views.service_add, name="service_add"),
    path(
        "<slug:organization_slug>/services/<int:pk>/edit/",
        views.service_edit,
        name="service_edit",
    ),
    path("<slug:organization_slug>/team/", views.team_list, name="team"),
    path("<slug:organization_slug>/team/invite/", views.team_invite, name="team_invite"),
    path(
        "<slug:organization_slug>/team/<int:pk>/remove/",
        views.team_remove,
        name="team_remove",
    ),
]
