from django.contrib import admin
from .models import Property

@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "city", "district", "price", "rooms",
                    "property_type", "is_active", "views_count", "reviews_count", "created_at")
    list_filter = ("city", "district", "property_type", "is_active", "created_at")
    search_fields = ("title", "description", "city", "district")
    ordering = ("-created_at",)
