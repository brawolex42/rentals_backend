from django.contrib import admin
from django.apps import apps


def get_model(name: str):
    try:
        return apps.get_model(apps.get_app_config("analytics").label, name)
    except Exception:
        return None


def has_field(model, name: str) -> bool:
    try:
        model._meta.get_field(name)
        return True
    except Exception:
        return False


def pick_cols(model, extras):
    cols = ["id"]
    for c in extras:
        if has_field(model, c):
            cols.append(c)
    return tuple(cols)


SearchQuery = get_model("SearchQuery")
ViewEvent = get_model("ViewEvent")

if SearchQuery:
    class SearchQueryAdmin(admin.ModelAdmin):
        list_display = pick_cols(SearchQuery, ["query", "q", "user", "session_key", "ip", "created_at", "timestamp"])
        search_fields = tuple(f for f in ["query", "q", "session_key", "ip"] if has_field(SearchQuery, f)) + (
            "user__username",
            "user__email",
        )
        date_hierarchy = (
            "created_at" if has_field(SearchQuery, "created_at")
            else ("timestamp" if has_field(SearchQuery, "timestamp") else None)
        )
    admin.site.register(SearchQuery, SearchQueryAdmin)

if ViewEvent:
    class ViewEventAdmin(admin.ModelAdmin):
        list_display = pick_cols(ViewEvent, ["property", "path", "url", "user", "session_key", "ip", "created_at", "timestamp"])
        search_fields = tuple(f for f in ["path", "url", "session_key", "ip"] if has_field(ViewEvent, f)) + (
            "user__username",
            "user__email",
            "property__title",
        )
        date_hierarchy = (
            "created_at" if has_field(ViewEvent, "created_at")
            else ("timestamp" if has_field(ViewEvent, "timestamp") else None)
        )
    admin.site.register(ViewEvent, ViewEventAdmin)

try:
    from src.properties.models import Property

    @admin.register(Property)
    class PropertyAdmin(admin.ModelAdmin):
        list_display = ("id", "title", "city", "postal_code", "address_line", "price", "rooms", "property_type", "is_active", "created_at")
        search_fields = ("title", "city", "district", "address_line", "postal_code")
        list_filter = ("city", "property_type", "is_active")
        ordering = ("-created_at",)
except Exception:
    pass
