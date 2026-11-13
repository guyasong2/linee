from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("register/", views.register, name="register"),
    path("register/person/", views.register_person, name="register_person"),
    path("register/organization/", views.register_organization, name="register_organization"),
    path("account/", views.account, name="account"),
]
