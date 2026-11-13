from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.core.exceptions import ValidationError

from .validators import normalize_phone


class EmailOrPhoneBackend(ModelBackend):
    """Authenticate staff with either their normalized phone or email address."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        if username is None:
            username = kwargs.get(UserModel.USERNAME_FIELD)
        if username is None or password is None:
            return None

        identifier = str(username).strip()
        if not identifier:
            return None

        try:
            if "@" in identifier:
                user = UserModel._default_manager.get(email__iexact=identifier)
            else:
                user = UserModel._default_manager.get(phone=normalize_phone(identifier))
        except (UserModel.DoesNotExist, UserModel.MultipleObjectsReturned, ValidationError):
            # Consume a hash even when the account does not exist, to reduce
            # the timing difference between an unknown and a known identifier.
            UserModel().set_password(password)
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def get_user(self, user_id):
        UserModel = get_user_model()
        try:
            return UserModel._default_manager.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None
