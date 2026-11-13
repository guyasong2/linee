from __future__ import annotations

from django.contrib.auth.base_user import BaseUserManager

from .validators import normalize_email, normalize_phone


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(
        self,
        phone: str | None,
        email: str | None,
        password: str | None,
        **extra_fields,
    ):
        normalized_phone = normalize_phone(phone)
        normalized_email = normalize_email(email)
        if not normalized_phone and not normalized_email:
            raise ValueError("A user needs a phone number or an email address.")

        user = self.model(
            phone=normalized_phone,
            email=normalized_email,
            **extra_fields,
        )
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(
        self,
        phone: str | None = None,
        email: str | None = None,
        password: str | None = None,
        **extra_fields,
    ):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(phone, email, password, **extra_fields)

    def create_superuser(
        self,
        phone: str | None = None,
        email: str | None = None,
        password: str | None = None,
        **extra_fields,
    ):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        if not password:
            raise ValueError("Superuser must have a password.")
        return self._create_user(phone, email, password, **extra_fields)
