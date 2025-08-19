from rest_framework import serializers
from django.utils import timezone
from django.db.models import Q

from .models import Booking
from src.shared.enums import BookingStatus


class BookingReadSerializer(serializers.ModelSerializer):
    """Удобный сериализатор для списка/детали (можно расширить при желании)."""
    class Meta:
        model = Booking
        fields = (
            "id",
            "property",
            "tenant",
            "start_date",
            "end_date",
            "status",
            "checkout_confirmed_at",
            "cancelled_at",
            "cancelled_by",
            "status_updated_at",
            "created_at",
        )
        read_only_fields = fields


class BookingCreateSerializer(serializers.ModelSerializer):
    """
    Создание брони:
    - end_date > start_date
    - нельзя в прошлом
    - нет пересечений с блокирующими статусами
    - tenant берём из request.user
    """
    class Meta:
        model = Booking
        fields = ("property", "start_date", "end_date")

    def validate(self, attrs):
        start = attrs.get("start_date")
        end = attrs.get("end_date")
        prop = attrs.get("property")
        today = timezone.localdate()

        if not start or not end or not prop:
            raise serializers.ValidationError("Не хватает данных для брони (property, start_date, end_date).")

        if start >= end:
            raise serializers.ValidationError({"end_date": "Дата выезда должна быть позже даты заезда."})

        # Запрет брони задним числом
        if start < today:
            raise serializers.ValidationError({"start_date": "Нельзя бронировать задним числом."})
        if end < today:
            raise serializers.ValidationError({"end_date": "Нельзя бронировать задним числом."})

        # Только статусы, реально блокирующие календарь
        blocking_statuses = [
            getattr(BookingStatus, 'PENDING', BookingStatus.PENDING),
            getattr(BookingStatus, 'CONFIRMED', BookingStatus.PENDING),
            getattr(BookingStatus, 'ACTIVE', BookingStatus.PENDING),
            getattr(BookingStatus, 'APPROVED', BookingStatus.PENDING),
            getattr(BookingStatus, 'BOOKED', BookingStatus.PENDING),
            getattr(BookingStatus, 'IN_PROGRESS', BookingStatus.PENDING),
        ]

        overlap = (
            Booking.objects
            .filter(property=prop, status__in=blocking_statuses)
            .filter(Q(start_date__lt=end) & Q(end_date__gt=start))
            .exists()
        )
        if overlap:
            raise serializers.ValidationError("На эти даты уже есть активная/ожидающая бронь.")

        return attrs

    def create(self, validated_data):
        # Привязываем текущего пользователя как арендатора
        request = self.context.get("request")
        if not request or not request.user or not request.user.is_authenticated:
            raise serializers.ValidationError("Требуется авторизация для создания брони.")
        validated_data["tenant"] = request.user
        return super().create(validated_data)


class BookingStatusSerializer(serializers.ModelSerializer):

    class Meta:
        model = Booking
        fields = ('id', 'status', 'checkout_confirmed_at')
        read_only_fields = ('id',)
