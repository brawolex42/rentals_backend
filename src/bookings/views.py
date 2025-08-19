from datetime import datetime
import logging
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.template import TemplateDoesNotExist
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views import View
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.utils.translation import gettext as _
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication
try:
    from rest_framework_simplejwt.authentication import JWTAuthentication
except Exception:
    JWTAuthentication = None
from .models import Booking
from src.properties.models import Property
from src.shared.enums import BookingStatus

logger = logging.getLogger(__name__)

def _status_value(name: str):
    member = getattr(BookingStatus, name, None)
    return getattr(member, "value", None)

def _choose_status(*preferred_names: str, fallback: str = "PENDING") -> str:
    for n in preferred_names:
        v = _status_value(n)
        if v:
            return v
    v_fallback = _status_value(fallback)
    if not v_fallback:
        return fallback
    return v_fallback

@require_POST
@login_required
def book_now(request, pk: int):
    prop = get_object_or_404(Property, pk=pk)
    start_str = request.POST.get('check_in') or request.POST.get('start_date')
    end_str = request.POST.get('check_out') or request.POST.get('end_date')
    guests_str = request.POST.get('guests') or "1"

    def parse_date(s):
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            return None

    def parse_int(s, default=1):
        try:
            v = int(s)
            if v < 1:
                return default
            return v
        except Exception:
            return default

    guests = parse_int(guests_str, 1)
    start_date = parse_date(start_str) if start_str else None
    end_date = parse_date(end_str) if end_str else None
    if not start_date or not end_date or end_date <= start_date:
        messages.error(request, _("Invalid dates."))
        return redirect(f"{reverse('property_detail', args=[prop.pk])}?start={start_str or ''}&end={end_str or ''}#book")
    today = timezone.localdate()
    if start_date < today:
        messages.error(request, _("You cannot book in the past."))
        return redirect(f"{reverse('property_detail', args=[prop.pk])}?start={start_date}&end={end_date}#book")
    overlapping_statuses = [s for s in {
        _status_value("PENDING"),
        _status_value("CONFIRMED"),
        _status_value("ACTIVE"),
        _status_value("APPROVED"),
        _status_value("BOOKED"),
        _status_value("IN_PROGRESS"),
    } if s]
    qs = Booking.objects.filter(property=prop)
    if overlapping_statuses:
        qs = qs.filter(status__in=overlapping_statuses)
    qs = qs.filter(start_date__lt=end_date, end_date__gt=start_date)
    if qs.exists():
        messages.error(request, _("These dates are already booked."))
        return redirect(f"{reverse('property_detail', args=[prop.pk])}?start={start_date}&end={end_date}#book")
    if start_date <= today <= end_date:
        initial_status = _choose_status("ACTIVE", "CONFIRMED", fallback="PENDING")
    else:
        initial_status = _choose_status("CONFIRMED", fallback="PENDING")
    create_kwargs = dict(
        property=prop,
        tenant=request.user,
        start_date=start_date,
        end_date=end_date,
        status=initial_status
    )
    field_names = {f.name for f in Booking._meta.get_fields()}
    for fname in ("guests", "persons", "people", "occupants"):
        if fname in field_names:
            create_kwargs[fname] = guests
            break
    Booking.objects.create(**create_kwargs)
    if getattr(prop, "owner", None) and prop.owner and prop.owner.email:
        ctx = {"property": prop, "tenant": request.user, "start_date": start_date, "end_date": end_date, "guests": guests}
        subj = f"New booking: {prop.title}"
        try:
            html = render_to_string("emails/new_booking.html", ctx)
        except TemplateDoesNotExist:
            html = None
        text = f"New booking for “{prop.title}”.\nDates: {start_date} — {end_date}\nGuests: {guests}\nClient: {request.user.get_username()} ({request.user.email})"
        msg = EmailMultiAlternatives(subj, text, settings.DEFAULT_FROM_EMAIL, [prop.owner.email])
        if html:
            msg.attach_alternative(html, "text/html")
        msg.send(fail_silently=True)
    messages.success(request, _("Booking created."))
    return redirect(f"{reverse('property_detail', args=[prop.pk])}#book")

class ConfirmCheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        b = get_object_or_404(Booking.objects.select_related('property__owner'), pk=pk)
        if not hasattr(b.property, 'owner') or b.property.owner_id != request.user.id:
            return Response({'detail': _('Forbidden')}, status=403)
        if b.checkout_confirmed_at is None:
            b.checkout_confirmed_at = timezone.now()
            b.status = _choose_status("COMPLETED", fallback=b.status)
            b.save(update_fields=['checkout_confirmed_at', 'status', 'status_updated_at'])
        return Response({'id': b.id, 'status': b.status, 'checkout_confirmed_at': b.checkout_confirmed_at})

class MarkOverdueView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        b = get_object_or_404(Booking.objects.select_related('property__owner', 'tenant'), pk=pk)
        if not hasattr(b.property, 'owner') or b.property.owner_id != request.user.id:
            return Response({'detail': _('Forbidden')}, status=403)
        b.status = _choose_status("OVERDUE", fallback=b.status)
        b.save(update_fields=['status', 'status_updated_at'])
        ctx = {'booking': b}
        subj = f'Overdue booking #{b.id}'
        html = render_to_string('emails/overdue_booking.html', ctx)
        text = render_to_string('emails/overdue_booking.txt', ctx)
        if getattr(b.tenant, "email", ""):
            m1 = EmailMultiAlternatives(subj, text, settings.DEFAULT_FROM_EMAIL, [b.tenant.email])
            m1.attach_alternative(html, "text/html")
            m1.send()
        if getattr(b.property, "owner", None) and getattr(b.property.owner, "email", ""):
            m2 = EmailMultiAlternatives(subj, text, settings.DEFAULT_FROM_EMAIL, [b.property.owner.email])
            m2.attach_alternative(html, "text/html")
            m2.send()
        return Response({'id': b.id, 'status': b.status})

class CancelBookingView(APIView):
    authentication_classes = [SessionAuthentication] + ([JWTAuthentication] if JWTAuthentication else [])
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        b = get_object_or_404(Booking.objects.select_related('property__owner', 'tenant'), pk=pk)
        if request.user.id == getattr(b.tenant, "id", None):
            actor = "TENANT"
        elif hasattr(b.property, "owner") and request.user.id == getattr(b.property.owner, "id", None):
            actor = "OWNER"
        elif request.user.is_staff or request.user.is_superuser:
            actor = "ADMIN"
        else:
            return Response({'detail': _('Forbidden')}, status=403)
        if getattr(BookingStatus, "CANCELLED", None) and b.status == BookingStatus.CANCELLED:
            return Response({'detail': _('Already cancelled')}, status=400)
        if getattr(BookingStatus, "COMPLETED", None) and b.status == BookingStatus.COMPLETED:
            return Response({'detail': _('Completed booking cannot be cancelled')}, status=400)
        b.status = _status_value("CANCELED") or b.status
        b.cancelled_at = timezone.now()
        b.cancelled_by = actor
        b.save(update_fields=['status', 'cancelled_at', 'cancelled_by', 'status_updated_at'])
        ctx = {'booking': b, 'actor': actor}
        subj = f"Booking cancelled #{b.id}"
        try:
            html = render_to_string('emails/cancelled_booking.html', ctx)
        except TemplateDoesNotExist:
            html = None
        text = f"Booking #{b.id} cancelled."
        recipients = []
        if getattr(b.tenant, "email", ""):
            recipients.append(b.tenant.email)
        if hasattr(b.property, "owner") and getattr(b.property.owner, "email", ""):
            recipients.append(b.property.owner.email)
        recipients = list(dict.fromkeys(recipients))
        if recipients:
            msg = EmailMultiAlternatives(subj, text, settings.DEFAULT_FROM_EMAIL, recipients)
            if html:
                msg.attach_alternative(html, "text/html")
            msg.send(fail_silently=True)
        return Response({'id': b.id, 'status': b.status, 'cancelled_at': b.cancelled_at, 'cancelled_by': b.cancelled_by})

@login_required
@require_POST
def cancel_booking_html(request, pk: int):
    b = get_object_or_404(Booking.objects.select_related('property__owner', 'tenant'), pk=pk, tenant=request.user)
    ok, _ = b.cancel(request.user)
    if ok:
        messages.success(request, _("Booking cancelled."))
    else:
        messages.error(request, _("Unable to cancel booking."))
    return redirect(reverse('my_bookings'))

class MyBookingsView(LoginRequiredMixin, TemplateView):
    template_name = "users/my_bookings.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = Booking.objects.filter(tenant=self.request.user).select_related('property').order_by('-created_at')
        ctx['bookings'] = qs
        return ctx

class EditBookingView(LoginRequiredMixin, View):
    template_name = "users/booking_edit.html"

    def get(self, request, pk: int):
        b = get_object_or_404(Booking.objects.select_related('property'), pk=pk, tenant=request.user)
        return render(request, self.template_name, {'booking': b})

    def post(self, request, pk: int):
        b = get_object_or_404(Booking.objects.select_related('property'), pk=pk, tenant=request.user)
        def parse_date(s):
            try:
                return datetime.strptime(s, "%Y-%m-%d").date()
            except Exception:
                return None
        start_str = request.POST.get('start_date')
        end_str = request.POST.get('end_date')
        new_start = parse_date(start_str) if start_str else None
        new_end = parse_date(end_str) if end_str else None
        if not new_start or not new_end or new_end <= new_start:
            return render(request, self.template_name, {'booking': b, 'error': _('Invalid dates')})
        today = timezone.localdate()
        if new_start < today:
            return render(request, self.template_name, {'booking': b, 'error': _('You cannot move booking to the past')})
        overlapping_statuses = [s for s in {
            _status_value("PENDING"),
            _status_value("CONFIRMED"),
            _status_value("ACTIVE"),
            _status_value("APPROVED"),
            _status_value("BOOKED"),
            _status_value("IN_PROGRESS"),
        } if s]
        qs = Booking.objects.filter(property=b.property).exclude(pk=b.pk)
        if overlapping_statuses:
            qs = qs.filter(status__in=overlapping_statuses)
        qs = qs.filter(start_date__lt=new_end, end_date__gt=new_start)
        if qs.exists():
            return render(request, self.template_name, {'booking': b, 'error': _('Dates are unavailable')})
        b.start_date = new_start
        b.end_date = new_end
        if new_start <= today <= new_end:
            b.status = _choose_status("ACTIVE", "CONFIRMED", fallback=b.status)
        else:
            b.status = _choose_status("CONFIRMED", fallback=b.status)
        b.save(update_fields=['start_date', 'end_date', 'status', 'status_updated_at'])
        try:
            html = render_to_string('emails/updated_booking.html', {'booking': b})
        except TemplateDoesNotExist:
            html = None
        text = f"Booking #{b.id} dates updated: {b.start_date} — {b.end_date}"
        recipients = []
        if getattr(b.tenant, "email", ""):
            recipients.append(b.tenant.email)
        if hasattr(b.property, "owner") and getattr(b.property.owner, "email", ""):
            recipients.append(b.property.owner.email)
        recipients = list(dict.fromkeys(recipients))
        if recipients:
            msg = EmailMultiAlternatives(f'Booking updated #{b.id}', text, settings.DEFAULT_FROM_EMAIL, recipients)
            if html:
                msg.attach_alternative(html, "text/html")
            msg.send(fail_silently=True)
        messages.success(request, _("Booking updated."))
        return redirect(reverse('my_bookings'))
