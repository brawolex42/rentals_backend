from rest_framework import serializers
from .models import Booking
from src.shared.enums import BookingStatus

class BookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = '__all__'
        read_only_fields = ('tenant', 'status', 'created_at')

    def validate(self, data):
        # базовые проверки дат
        start = data.get('start_date') or getattr(self.instance, 'start_date', None)
        end = data.get('end_date') or getattr(self.instance, 'end_date', None)
        prop = data.get('property') or getattr(self.instance, 'property', None)
        tenant = self.context['request'].user if self.context and self.context.get('request') else None

        if not start or not end or not prop:
            return data

        if end <= start:
            raise serializers.ValidationError("end_date должен быть позднее start_date.")

        # арендатор не может бронировать своё объявление
        if tenant and prop.owner_id == tenant.id:
            raise serializers.ValidationError("Нельзя бронировать собственный объект.")

        # запрет пересечений (включая pending/confirmed)
        qs = Booking.objects.filter(property=prop, status__in=[BookingStatus.PENDING, BookingStatus.CONFIRMED])
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        # интервалы пересекаются, если (startA < endB) и (startB < endA)
        qs = qs.filter(start_date__lt=end, end_date__gt=start)
        if qs.exists():
            raise serializers.ValidationError("Даты пересекаются с существующим бронированием.")

        return data
