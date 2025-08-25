from django.contrib import admin, messages
from django.urls import path, reverse
from django.shortcuts import redirect, get_object_or_404
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.template import TemplateDoesNotExist
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.core.exceptions import ValidationError

from .models import Booking
from src.shared.enums import BookingStatus


@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = (
        'id','property','tenant','start_date','end_date','status',
        'cancelled_by','created_at','checkout_confirmed_at','admin_actions',
    )
    list_filter = ('status','start_date','end_date','created_at','cancelled_by')
    search_fields = ('property__title','tenant__username','tenant__email')
    actions = ('send_to_owner','cancel_selected','confirm_checkout_selected')
    readonly_fields = (
        'email_preview','checkout_confirmed_at',
        'cancelled_at','cancelled_by','status_updated_at','created_at'
    )
    change_form_template = "admin/bookings/booking/change_form.html"
    list_select_related = ('property','tenant','property__owner')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('property','tenant','property__owner')

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            self._send_owner_email(request, obj)

    def send_to_owner(self, request, queryset):
        sent = 0
        for b in queryset.select_related('property__owner','tenant'):
            if self._send_owner_email(request, b):
                sent += 1
        self.message_user(request, f'Отправлено писем: {sent}', level=messages.SUCCESS)
    send_to_owner.short_description = 'Отправить письмо владельцу о бронировании'

    def cancel_selected(self, request, queryset):
        changed = 0
        for b in queryset.select_related('property__owner','tenant'):
            if b.status in (getattr(BookingStatus, "CANCELLED", None), getattr(BookingStatus, "COMPLETED", None)):
                continue
            self._cancel_booking(request, b, actor="ADMIN")
            changed += 1
        self.message_user(request, f'Отменено броней: {changed}', level=messages.SUCCESS)
    cancel_selected.short_description = 'Отменить выбранные брони'

    def confirm_checkout_selected(self, request, queryset):
        updated = 0
        for b in queryset:
            try:
                b.confirm_checkout(by_user=request.user)
                updated += 1
            except ValidationError as e:
                self.message_user(request, f"Booking #{b.id}: {e}", level=messages.WARNING)
        if updated:
            self.message_user(request, f"Подтверждён выезд у {updated} бронирований.", level=messages.SUCCESS)
    confirm_checkout_selected.short_description = "Подтвердить выезд"

    def _send_owner_email(self, request, booking: Booking) -> bool:
        owner = getattr(booking.property, 'owner', None)
        to_email = getattr(owner, 'email', '') if owner else ''
        if not to_email:
            self.message_user(request, f'Нет e-mail владельца для брони #{booking.id}', level=messages.WARNING)
            return False
        ctx = {'property': booking.property,'tenant': booking.tenant,'start_date': booking.start_date,'end_date': booking.end_date}
        subject = f'Новая бронь: {booking.property.title}'
        text = (
            f"Новая бронь по объекту «{booking.property.title}».\n"
            f"Даты: {booking.start_date} — {booking.end_date}\n"
            f"Клиент: {booking.tenant.get_username()} ({booking.tenant.email})"
        )
        try:
            html = render_to_string('emails/new_booking.html', ctx)
        except TemplateDoesNotExist:
            html = None
        msg = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [to_email])
        if html:
            msg.attach_alternative(html, 'text/html')
        msg.send(fail_silently=True)
        return True

    def _cancel_booking(self, request, booking: Booking, actor: str):
        if booking.status in (getattr(BookingStatus, "CANCELLED", None), getattr(BookingStatus, "COMPLETED", None)):
            return False
        booking.status = getattr(BookingStatus, "CANCELLED", booking.status)
        booking.cancelled_at = timezone.now()
        booking.cancelled_by = actor
        booking.save(update_fields=['status','cancelled_at','cancelled_by','status_updated_at'])
        ctx = {'booking': booking, 'actor': actor}
        subject = f'Отмена бронирования #{booking.id}'
        try:
            html = render_to_string('emails/cancelled_booking.html', ctx)
        except TemplateDoesNotExist:
            html = None
        text = render_to_string('emails/cancelled_booking.txt', ctx) if not html else f"Бронь #{booking.id} отменена."
        recipients = []
        if getattr(booking.tenant, "email", ""):
            recipients.append(booking.tenant.email)
        owner = getattr(booking.property, 'owner', None)
        if getattr(owner, "email", ""):
            recipients.append(owner.email)
        recipients = list(dict.fromkeys(recipients))
        if recipients:
            msg = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, recipients)
            if html:
                msg.attach_alternative(html, "text/html")
            msg.send(fail_silently=True)
        return True

    def email_preview(self, obj):
        if not obj or not obj.pk:
            return ""
        ctx = {'property': obj.property,'tenant': obj.tenant,'start_date': obj.start_date,'end_date': obj.end_date}
        try:
            html = render_to_string('emails/new_booking.html', ctx)
        except TemplateDoesNotExist:
            html = (
                f"<h2>Новая бронь</h2>"
                f"<p><strong>Объект:</strong> {obj.property}</p>"
                f"<p><strong>Даты:</strong> {obj.start_date} — {obj.end_date}</p>"
                f"<p><strong>Клиент:</strong> {obj.tenant.get_username()} "
                f"{'&lt;'+obj.tenant.email+'&gt;' if obj.tenant.email else ''}</p>"
            )
        return mark_safe(f'<div style="border:1px solid #ddd;border-radius:8px;padding:12px;margin-top:8px;">{html}</div>')
    email_preview.short_description = "Превью письма владельцу"

    def admin_actions(self, obj):
        try:
            send_url = reverse('admin:bookings_booking_send_owner_email', args=[obj.pk])
            cancel_btn = ''
            checkout_btn = ''
            if obj.status not in (getattr(BookingStatus, "CANCELLED", None), getattr(BookingStatus, "COMPLETED", None)):
                cancel_url = reverse('admin:bookings_booking_cancel', args=[obj.pk])
                cancel_btn = f'<a class="button" style="background:#ef4444;color:#fff" href="{cancel_url}">Отменить</a>'
            if not obj.checkout_confirmed_at:
                checkout_url = reverse('admin:bookings_booking_checkout', args=[obj.pk])
                checkout_btn = f'<a class="button" style="background:#10b981;color:#fff" href="{checkout_url}">Выезд</a>'
            return mark_safe(f'<a class="button" href="{send_url}">Письмо</a> {cancel_btn} {checkout_btn}')
        except Exception:
            return '-'
    admin_actions.short_description = "Действия"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '<path:object_id>/send-owner-email/',
                self.admin_site.admin_view(self.send_owner_email_view),
                name='bookings_booking_send_owner_email',
            ),
            path(
                '<path:object_id>/cancel/',
                self.admin_site.admin_view(self.cancel_booking_view),
                name='bookings_booking_cancel',
            ),
            path(
                '<path:object_id>/checkout/',
                self.admin_site.admin_view(self.confirm_checkout_view),
                name='bookings_booking_checkout',
            ),
        ]
        return custom + urls

    def send_owner_email_view(self, request, object_id: str):
        booking = get_object_or_404(Booking.objects.select_related('property__owner','tenant'), pk=object_id)
        ok = self._send_owner_email(request, booking)
        if ok:
            self.message_user(request, f'Письмо отправлено владельцу: {booking.property}', messages.SUCCESS)
        return redirect(reverse('admin:bookings_booking_change', args=[booking.pk]))

    def cancel_booking_view(self, request, object_id: str):
        booking = get_object_or_404(Booking.objects.select_related('property__owner','tenant'), pk=object_id)
        if self._cancel_booking(request, booking, actor="ADMIN"):
            self.message_user(request, f'Бронь #{booking.pk} отменена.', messages.SUCCESS)
        return redirect(reverse('admin:bookings_booking_change', args=[booking.pk]))

    def confirm_checkout_view(self, request, object_id: str):
        booking = get_object_or_404(Booking.objects.select_related('property__owner','tenant'), pk=object_id)
        try:
            booking.confirm_checkout(by_user=request.user)
            self.message_user(request, f'Выезд по брони #{booking.pk} подтверждён.', messages.SUCCESS)
        except ValidationError as e:
            self.message_user(request, f'Ошибка: {e}', messages.WARNING)
        return redirect(reverse('admin:bookings_booking_change', args=[booking.pk]))
