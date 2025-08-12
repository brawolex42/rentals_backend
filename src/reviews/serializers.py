from rest_framework import serializers
from .models import Review
from src.shared.enums import BookingStatus
from src.bookings.models import Booking

class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = '__all__'
        read_only_fields = ('author', 'created_at')

    def validate_rating(self, value):
        if not (1 <= value <= 5):
            raise serializers.ValidationError("Рейтинг должен быть в диапазоне 1..5.")
        return value

    def validate(self, data):
        request = self.context.get('request')
        if not request or not request.user or not request.user.is_authenticated:
            raise serializers.ValidationError("Требуется аутентификация.")

        prop = data.get('property')
        if not prop:
            return data

        # хотя бы одно подтверждённое бронирование для этого объекта
        has_booking = Booking.objects.filter(
            property=prop,
            tenant=request.user,
            status=BookingStatus.CONFIRMED
        ).exists()

        if not has_booking:
            raise serializers.ValidationError("Оставлять отзыв могут только пользователи с подтверждённым бронированием этой недвижимости.")
        return data
