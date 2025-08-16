from rest_framework import serializers
from .models import Booking

class BookingStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = ('id','status','checkout_confirmed_at')
        read_only_fields = ('id',)
