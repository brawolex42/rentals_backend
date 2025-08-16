from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings

from src.bookings.models import Booking
from src.shared.enums import BookingStatus

class Command(BaseCommand):
    def handle(self, *args, **options):
        today = timezone.localdate()
        qs = Booking.objects.select_related('property__owner','tenant')
        for b in qs:
            updated = False
            if b.checkout_confirmed_at:
                if b.status != BookingStatus.COMPLETED:
                    b.status = BookingStatus.COMPLETED
                    updated = True
            else:
                if b.end_date < today and b.status not in (BookingStatus.CANCELLED, BookingStatus.COMPLETED):
                    if b.status != BookingStatus.OVERDUE:
                        b.status = BookingStatus.OVERDUE
                        updated = True
                        ctx = {'booking': b}
                        subj = f'Бронь просрочена: #{b.id}'
                        html = render_to_string('emails/overdue_booking.html', ctx)
                        text = render_to_string('emails/overdue_booking.txt', ctx)
                        if b.tenant.email:
                            m1 = EmailMultiAlternatives(subj, text, settings.DEFAULT_FROM_EMAIL, [b.tenant.email])
                            m1.attach_alternative(html, "text/html")
                            m1.send()
                        if hasattr(b.property, 'owner') and b.property.owner and b.property.owner.email:
                            m2 = EmailMultiAlternatives(subj, text, settings.DEFAULT_FROM_EMAIL, [b.property.owner.email])
                            m2.attach_alternative(html, "text/html")
                            m2.send()
                elif b.start_date <= today <= b.end_date:
                    if b.status not in (BookingStatus.ACTIVE, BookingStatus.CANCELLED, BookingStatus.COMPLETED):
                        b.status = BookingStatus.ACTIVE
                        updated = True
                elif today < b.start_date:
                    if b.status not in (BookingStatus.CONFIRMED, BookingStatus.CANCELLED, BookingStatus.COMPLETED):
                        b.status = BookingStatus.CONFIRMED
                        updated = True
            if updated:
                b.save(update_fields=['status','status_updated_at'])
