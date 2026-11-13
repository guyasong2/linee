from __future__ import annotations

import phonenumbers
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email


def normalize_phone(value: str | None, *, region: str | None = None) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None

    region = region or getattr(settings, "PHONE_DEFAULT_REGION", "CM")
    try:
        number = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException as exc:
        raise ValidationError("Enter a valid phone number, including the country code.") from exc

    if not phonenumbers.is_valid_number(number):
        raise ValidationError("Enter a valid phone number, including the country code.")

    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)


def normalize_email(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if not normalized:
        return None
    validate_email(normalized)
    return normalized
