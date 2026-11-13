from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "action",
        "resource_type",
        "actor",
        "organization",
        "request_id",
    )
    list_filter = ("action", "resource_type", "organization")
    search_fields = ("action", "resource_type", "resource_public_id", "request_id")
    date_hierarchy = "created_at"
    readonly_fields = (
        "organization",
        "actor",
        "action",
        "resource_type",
        "resource_public_id",
        "before",
        "after",
        "reason",
        "request_id",
        "ip_address",
        "user_agent",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
