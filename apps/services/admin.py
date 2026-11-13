from django.contrib import admin

from .models import BranchService, Service, ServiceFee


class ServiceFeeInline(admin.TabularInline):
    model = ServiceFee
    extra = 0
    fields = (
        "amount_xaf",
        "currency",
        "effective_from",
        "effective_to",
        "is_active",
        "published_at",
    )


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name_en", "code", "organization", "category", "is_active")
    list_filter = ("category", "is_active", "organization")
    search_fields = ("name_en", "name_fr", "code", "organization__name")
    autocomplete_fields = ("organization",)


@admin.register(BranchService)
class BranchServiceAdmin(admin.ModelAdmin):
    list_display = (
        "service",
        "branch",
        "organization",
        "default_duration_minutes",
        "is_active",
    )
    list_filter = ("is_active", "organization", "branch")
    search_fields = (
        "service__name_en",
        "service__name_fr",
        "branch__name",
        "organization__name",
    )
    autocomplete_fields = ("organization", "branch", "service")
    inlines = (ServiceFeeInline,)


@admin.register(ServiceFee)
class ServiceFeeAdmin(admin.ModelAdmin):
    list_display = (
        "branch_service",
        "amount_xaf",
        "currency",
        "effective_from",
        "effective_to",
        "is_active",
        "published_at",
    )
    list_filter = ("is_active", "currency", "organization")
    search_fields = ("branch_service__service__name_en", "branch_service__branch__name")
    autocomplete_fields = ("organization", "branch_service", "approved_by")
    date_hierarchy = "effective_from"
