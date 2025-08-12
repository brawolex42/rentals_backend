from django.contrib import admin
from .models import Review

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("id", "property", "author", "rating", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("property__title", "author__email")
    ordering = ("-created_at",)
