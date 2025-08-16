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

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

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

    def parse_date(s):
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            return None

    start_date = parse_date(start_str) if start_str else None
    end_date = parse_date(end_str) if end_str else None

    if not start_date or not end_date or start_date > end_date:
        return redirect(reverse('property_detail', args=[prop.pk]))

    overlapping_statuses = [
        s for s in {
            _status_value("PENDING"),
            _status_value("CONFIRMED"),
            _status_value("ACTIVE"),
            _status_value("APPROVED"),
            _status_value("BOOKED"),
            _status_value("IN_PROGRESS"),
        } if s
    ]

    qs = Booking.objects.filter(property=prop)
    if overlapping_statuses:
        qs = qs.filter(status__in=overlapping_statuses)
    qs = qs.filter(start_date__lte=end_date, end_date__gte=start_date)

    if qs.exists():
        return redirect(reverse('property_detail', args=[prop.pk]))

    today = timezone.localdate()
    if end_date < today:
        initial_status = _choose_status("CONFIRMED", fallback="PENDING")
    elif start_date <= today <= end_date:
        initial_status = _choose_status("ACTIVE", "CONFIRMED", fallback="PENDING")
    else:
        initial_status = _choose_status("CONFIRMED", fallback="PENDING")

    Booking.objects.create(
        property=prop,
        tenant=request.user,
        start_date=start_date,
        end_date=end_date,
        status=initial_status
    )

    if getattr(prop, "owner", None) and prop.owner and prop.owner.email:
        ctx = {
            "property": prop,
            "tenant": request.user,
            "start_date": start_date,
            "end_date": end_date,
        }
        subj = f"Новая бронь: {prop.title}"
        try:
            html = render_to_string("emails/new_booking.html", ctx)
        except TemplateDoesNotExist:
            html = None
        text = (
            f"Новая бронь по объекту «{prop.title}».\n"
            f"Даты: {start_date} — {end_date}\n"
            f"Клиент: {request.user.get_username()} ({request.user.email})"
        )
        msg = EmailMultiAlternatives(subj, text, settings.DEFAULT_FROM_EMAIL, [prop.owner.email])
        if html:
            msg.attach_alternative(html, "text/html")
        msg.send(fail_silently=True)

    return redirect(reverse('property_detail', args=[prop.pk]))


class ConfirmCheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk: int):
        b = get_object_or_404(Booking.objects.select_related('property__owner'), pk=pk)
        if not hasattr(b.property, 'owner') or b.property.owner_id != request.user.id:
            return Response({'detail': 'Недостаточно прав'}, status=403)
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
            return Response({'detail': 'Недостаточно прав'}, status=403)

        b.status = _choose_status("OVERDUE", fallback=b.status)
        b.save(update_fields=['status', 'status_updated_at'])

        ctx = {'booking': b}
        subj = f'Просрочено бронирование #{b.id}'
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
            return Response({'detail': 'Недостаточно прав'}, status=403)

        if getattr(BookingStatus, "CANCELLED", None) and b.status == BookingStatus.CANCELLED:
            return Response({'detail': 'Бронь уже отменена'}, status=400)
        if getattr(BookingStatus, "COMPLETED", None) and b.status == BookingStatus.COMPLETED:
            return Response({'detail': 'Завершённую бронь нельзя отменить'}, status=400)

        b.status = getattr(BookingStatus, "CANCELLED", b.status)
        b.cancelled_at = timezone.now()
        b.cancelled_by = actor
        b.save(update_fields=['status', 'cancelled_at', 'cancelled_by', 'status_updated_at'])

        ctx = {'booking': b, 'actor': actor}
        subj = f"Отмена бронирования #{b.id}"
        try:
            html = render_to_string('emails/cancelled_booking.html', ctx)
        except TemplateDoesNotExist:
            html = None
        text = render_to_string('emails/cancelled_booking.txt', ctx) if not html else f"Бронь #{b.id} отменена."

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


class MyBookingsView(LoginRequiredMixin, TemplateView):
    template_name = "users/my_bookings.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = (
            Booking.objects
            .filter(tenant=self.request.user)
            .select_related('property')
            .order_by('-created_at')
        )
        ctx['bookings'] = qs
        return ctx


class EditBookingView(LoginRequiredMixin, View):
    template_name = "users/booking_edit.html"

    def get(self, request, pk: int):
        b = get_object_or_404(Booking.objects.select_related('property'), pk=pk, tenant=request.user)
        return render(request, self.template_name, {'booking': b})

    def post(self, request, pk: int):
        b = get_object_or_404(Booking.objects.select_related('property'), pk=pk, tenant=request.user)
        start_str = request.POST.get('start_date')
        end_str = request.POST.get('end_date')

        def parse_date(s):
            try:
                return datetime.strptime(s, "%Y-%m-%d").date()
            except Exception:
                return None

        new_start = parse_date(start_str) if start_str else None
        new_end = parse_date(end_str) if end_str else None

        if not new_start or not new_end or new_start > new_end:
            return render(request, self.template_name, {'booking': b, 'error': 'Некорректные даты'})

        overlapping_statuses = [
            s for s in {
                _status_value("PENDING"),
                _status_value("CONFIRMED"),
                _status_value("ACTIVE"),
                _status_value("APPROVED"),
                _status_value("BOOKED"),
                _status_value("IN_PROGRESS"),
            } if s
        ]

        qs = Booking.objects.filter(property=b.property).exclude(pk=b.pk)
        if overlapping_statuses:
            qs = qs.filter(status__in=overlapping_statuses)
        qs = qs.filter(start_date__lte=new_end, end_date__gte=new_start)

        if qs.exists():
            return render(request, self.template_name, {'booking': b, 'error': 'Даты заняты. Выберите другой период.'})

        b.start_date = new_start
        b.end_date = new_end

        today = timezone.localdate()
        if new_end < today:
            b.status = _choose_status("CONFIRMED", fallback=b.status)
        elif new_start <= today <= new_end:
            b.status = _choose_status("ACTIVE", "CONFIRMED", fallback=b.status)
        else:
            b.status = _choose_status("CONFIRMED", fallback=b.status)

        b.save(update_fields=['start_date', 'end_date', 'status', 'status_updated_at'])

        try:
            html = render_to_string('emails/updated_booking.html', {'booking': b})
        except TemplateDoesNotExist:
            html = None
        text = f"Изменены даты брони #{b.id}: {b.start_date} — {b.end_date}"

        recipients = []
        if getattr(b.tenant, "email", ""):
            recipients.append(b.tenant.email)
        if hasattr(b.property, "owner") and getattr(b.property.owner, "email", ""):
            recipients.append(b.property.owner.email)
        recipients = list(dict.fromkeys(recipients))
        if recipients:
            msg = EmailMultiAlternatives(f'Изменение брони #{b.id}', text, settings.DEFAULT_FROM_EMAIL, recipients)
            if html:
                msg.attach_alternative(html, "text/html")
            msg.send(fail_silently=True)

        return redirect(reverse('my_bookings'))
