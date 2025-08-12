from django.contrib import admin
from .models import Booking

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("id", "property", "tenant", "start_date", "end_date", "status", "created_at")
    list_filter = ("status", "start_date", "end_date", "created_at")
    search_fields = ("property__title", "tenant__email", "tenant__first_name", "tenant__last_name")
    ordering = ("-created_at",)
