from django.contrib import admin

from .models import InspectorProfile, ScheduleEntry, User


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("username", "role")
    search_fields = ("username",)
    list_filter = ("role",)


@admin.register(InspectorProfile)
class InspectorProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "user", "is_active")
    list_filter = ("is_active",)
    search_fields = ("full_name", "user__username")


@admin.register(ScheduleEntry)
class ScheduleEntryAdmin(admin.ModelAdmin):
    list_display = ("date", "inspector", "entry_type", "status", "sa_number")
    list_filter = ("entry_type", "status", "inspection_type", "date", "inspector__is_active")
    search_fields = ("inspector__full_name", "sa_number", "content")
    ordering = ("-date", "inspector__full_name")
    autocomplete_fields = ("inspector", "concluded_by")
