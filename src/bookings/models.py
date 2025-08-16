from django.db import models
from django.conf import settings
from django.utils import timezone
from src.properties.models import Property
from src.shared.enums import BookingStatus

class Booking(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name='bookings')
    tenant = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bookings')
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=16, choices=BookingStatus.choices, default=BookingStatus.PENDING)
    checkout_confirmed_at = models.DateTimeField(blank=True, null=True)
    cancelled_at = models.DateTimeField(blank=True, null=True)
    cancelled_by = models.CharField(max_length=10, blank=True, default='')
    status_updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['start_date', 'end_date']),
        ]

    def __str__(self):
        return f"{self.property.title} ({self.start_date}→{self.end_date}) [{self.status}]"

    def is_overdue_checkout(self):
        today = timezone.localdate()
        return self.end_date < today and self.checkout_confirmed_at is None and self.status != BookingStatus.CANCELLED

    def should_be_active(self):
        today = timezone.localdate()
        return self.start_date <= today <= self.end_date and self.status not in (BookingStatus.CANCELLED, BookingStatus.COMPLETED)

    def should_be_confirmed(self):
        today = timezone.localdate()
        return today < self.start_date and self.status not in (BookingStatus.CANCELLED, BookingStatus.COMPLETED)
