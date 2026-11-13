from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .managers import UserManager
from .validators import normalize_email, normalize_phone


class User(AbstractBaseUser, PermissionsMixin):
    class Language(models.TextChoices):
        ENGLISH = "en", "English"
        FRENCH = "fr", "Français"

    phone = models.CharField(max_length=20, unique=True, null=True, blank=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    full_name = models.CharField(max_length=150, blank=True)
    preferred_language = models.CharField(
        max_length=2, choices=Language.choices, default=Language.ENGLISH
    )
    is_platform_admin = models.BooleanField(
        default=False,
        help_text="Grants access to the restricted platform administration area.",
    )
    is_staff = models.BooleanField(
        default=False,
        help_text="Grants access to the Django administration site.",
    )
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS: list[str] = []
    EMAIL_FIELD = "email"

    class Meta:
        ordering = ("-date_joined",)
        constraints = [
            models.CheckConstraint(
                condition=Q(phone__isnull=False) | Q(email__isnull=False),
                name="user_requires_phone_or_email",
            )
        ]
        indexes = [
            models.Index(fields=("phone",), name="user_phone_idx"),
            models.Index(fields=("email",), name="user_email_idx"),
        ]
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self) -> str:
        return self.full_name or self.phone or self.email or f"User {self.pk}"

    def clean(self) -> None:
        super().clean()
        self.phone = normalize_phone(self.phone)
        self.email = normalize_email(self.email)
        if not self.phone and not self.email:
            raise ValidationError("A user needs a phone number or an email address.")

    def save(self, *args, **kwargs):
        self.phone = normalize_phone(self.phone)
        self.email = normalize_email(self.email)
        super().save(*args, **kwargs)

    def get_full_name(self) -> str:
        return self.full_name or self.get_short_name()

    def get_short_name(self) -> str:
        return self.full_name.split()[0] if self.full_name else (self.phone or self.email or "")
