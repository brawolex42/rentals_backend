from rest_framework import serializers
from .models import Property

class PropertySerializer(serializers.ModelSerializer):
    class Meta:
        model = Property
        fields = (
            'id',
            'owner',
            'title',
            'description',
            'city',
            'district',
            'address_line',
            'postal_code',
            'price',
            'rooms',
            'property_type',
            'is_active',
            'views_count',
            'reviews_count',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'owner',
            'views_count',
            'reviews_count',
            'created_at',
            'updated_at',
        )
