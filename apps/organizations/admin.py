from django.contrib import admin

from .models import Branch, Organization, OrganizationMembership


class BranchInline(admin.TabularInline):
    model = Branch
    extra = 0
    fields = ("name", "code", "status", "city", "address")


class MembershipInline(admin.TabularInline):
    model = OrganizationMembership
    extra = 0
    fields = ("user", "branch", "role", "is_active")
    autocomplete_fields = ("user",)


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "organization_type", "status", "city", "default_language")
    list_filter = ("status", "organization_type", "default_language", "city")
    search_fields = ("name", "slug", "legal_name")
    prepopulated_fields = {"slug": ("name",)}
    inlines = (BranchInline, MembershipInline)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "organization", "status", "city")
    list_filter = ("status", "organization", "city")
    search_fields = ("name", "code", "organization__name", "address")
    autocomplete_fields = ("organization",)


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "branch", "role", "is_active")
    list_filter = ("role", "is_active", "organization")
    search_fields = ("user__phone", "user__email", "user__full_name", "organization__name")
    autocomplete_fields = ("organization", "branch", "user")
