import builtins
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
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

    def clean(self):
        errors = {}
        today = timezone.localdate()
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            errors['end_date'] = _('Check-out date must be after check-in date.')
        if self.start_date and self.start_date < today:
            errors.setdefault('start_date', _('You cannot book in the past.'))
        if self.end_date and self.end_date < today:
            errors.setdefault('end_date', _('You cannot book in the past.'))
        if self.property_id and self.start_date and self.end_date:
            blocking_statuses = [
                getattr(BookingStatus, 'PENDING', BookingStatus.PENDING),
                getattr(BookingStatus, 'CONFIRMED', BookingStatus.PENDING),
                getattr(BookingStatus, 'ACTIVE', BookingStatus.PENDING),
                getattr(BookingStatus, 'APPROVED', BookingStatus.PENDING),
                getattr(BookingStatus, 'BOOKED', BookingStatus.PENDING),
                getattr(BookingStatus, 'IN_PROGRESS', BookingStatus.PENDING),
            ]
            conflict = (
                Booking.objects
                .filter(property_id=self.property_id, status__in=blocking_statuses)
                .exclude(pk=self.pk)
                .filter(Q(start_date__lt=self.end_date) & Q(end_date__gt=self.start_date))
                .exists()
            )
            if conflict:
                errors['start_date'] = _('These dates are already booked.')
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        should_validate = not update_fields or any(f in update_fields for f in ('property', 'start_date', 'end_date'))
        if should_validate:
            self.full_clean()
        return super().save(*args, **kwargs)

    def is_overdue_checkout(self):
        today = timezone.localdate()
        return self.end_date < today and self.checkout_confirmed_at is None and self.status not in (BookingStatus.CANCELLED, BookingStatus.CANCELED)

    def should_be_active(self):
        today = timezone.localdate()
        return self.start_date <= today <= self.end_date and self.status not in (BookingStatus.CANCELLED, BookingStatus.CANCELED, BookingStatus.COMPLETED)

    def should_be_confirmed(self):
        today = timezone.localdate()
        return today < self.start_date and self.status not in (BookingStatus.CANCELLED, BookingStatus.CANCELED, BookingStatus.COMPLETED)

    @builtins.property
    def is_cancelled(self) -> bool:
        return self.status in (BookingStatus.CANCELLED, BookingStatus.CANCELED) or self.cancelled_at is not None

    @builtins.property
    def is_active(self) -> bool:
        return not self.is_cancelled and self.end_date > timezone.localdate()

    def can_cancel(self, by_user) -> bool:
        if not by_user or not getattr(by_user, "is_authenticated", False):
            return False
        is_owner_or_staff = (self.tenant_id == getattr(by_user, "id", None)) or getattr(by_user, "is_staff", False)
        not_too_late = True
        if self.start_date:
            not_too_late = self.start_date > timezone.localdate()
        return is_owner_or_staff and not self.is_cancelled and not_too_late

    def cancel(self, by_user):
        if self.is_cancelled:
            return False, _("Booking is already cancelled.")
        if not self.can_cancel(by_user):
            return False, _("You cannot cancel this booking or it is too late.")
        self.cancelled_at = timezone.now()
        self.cancelled_by = "staff" if getattr(by_user, "is_staff", False) else "user"
        self.status = BookingStatus.CANCELLED
        self.save(update_fields=["cancelled_at", "cancelled_by", "status", "status_updated_at"])
        return True, _("Booking cancelled successfully.")

    def can_confirm_checkout(self) -> bool:
        if self.is_cancelled:
            return False
        return self.checkout_confirmed_at is None

    def confirm_checkout(self, by_user=None):
        if not self.can_confirm_checkout():
            raise ValidationError(_("Checkout has already been confirmed or booking is cancelled."))
        self.checkout_confirmed_at = timezone.now()
        try:
            if hasattr(BookingStatus, "COMPLETED"):
                self.status = BookingStatus.COMPLETED
        except Exception:
            pass
        self.save(update_fields=["checkout_confirmed_at", "status", "status_updated_at"])
