from django.contrib import admin
from .models import SearchQuery, ViewEvent

@admin.register(SearchQuery)
class SearchQueryAdmin(admin.ModelAdmin):
    list_display = ("id", "query", "user", "created_at")
    list_filter = ("created_at",)
    search_fields = ("query", "user__email")
    ordering = ("-created_at",)
    readonly_fields = ("query", "user", "created_at")

@admin.register(ViewEvent)
class ViewEventAdmin(admin.ModelAdmin):
    list_display = ("id", "property", "user", "created_at")
    list_filter = ("created_at",)
    search_fields = ("property__title", "user__email")
    ordering = ("-created_at",)
    readonly_fields = ("property", "user", "created_at")
