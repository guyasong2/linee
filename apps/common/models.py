import uuid

from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class PublicIdModel(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, db_index=True)

    class Meta:
        abstract = True


class TenantScopedModel(TimeStampedModel):
    """Base for every tenant-owned business table.

    The concrete model must declare an ``organization`` ForeignKey so that
    related_name and on_delete behaviour stay explicit at the domain boundary.
    This abstract class only documents and centralises the timestamp contract.
    """

    class Meta:
        abstract = True
