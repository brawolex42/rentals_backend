from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.apps import apps
from src.properties.models import Property
from src.shared.enums import BookingStatus


class Review(models.Model):
    property = models.ForeignKey(Property, related_name="reviews", on_delete=models.CASCADE)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="reviews", on_delete=models.CASCADE)
    rating = models.PositiveSmallIntegerField()
    text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["property", "author"], name="unique_review_per_user_per_property"),
        ]

    def __str__(self):
        dn = self.author.get_display_name() if hasattr(self.author, "get_display_name") else self.author.username
        return f"★{self.rating} {self.property.title} — {dn}"

    def clean(self):
        errors = {}
        if not (1 <= int(self.rating or 0) <= 5):
            errors["rating"] = _("Rating must be between 1 and 5.")
        today = timezone.localdate()
        Booking = apps.get_model('bookings', 'Booking')
        has_started_stay = Booking.objects.filter(
            property=self.property,
            tenant=self.author,
        ).exclude(
            status__in=[BookingStatus.CANCELLED, BookingStatus.CANCELED]
        ).filter(
            start_date__lte=today
        ).exists()
        if not has_started_stay:
            errors["property"] = _("You can leave a review only after your stay has started.")
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
