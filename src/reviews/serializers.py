from rest_framework import serializers
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.apps import apps
from src.properties.models import Property
from src.shared.enums import BookingStatus
from .models import Review


class ReviewAuthorSafeSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    display_name = serializers.SerializerMethodField()
    def get_display_name(self, obj):
        if hasattr(obj, "get_display_name"):
            return obj.get_display_name()
        name = (getattr(obj, "first_name", "") + " " + getattr(obj, "last_name", "")).strip()
        return name or getattr(obj, "username", "User")


class ReviewSerializer(serializers.ModelSerializer):
    author = ReviewAuthorSafeSerializer(read_only=True)
    class Meta:
        model = Review
        fields = ["id", "property", "author", "rating", "text", "created_at", "updated_at"]
        read_only_fields = ["id", "author", "created_at", "updated_at"]


class ReviewCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ["property", "rating", "text"]

    def validate(self, attrs):
        user = self.context["request"].user
        prop = attrs.get("property")
        rating = int(attrs.get("rating") or 0)
        if not isinstance(prop, Property):
            raise serializers.ValidationError({"property": _("Invalid property.")})
        if not (1 <= rating <= 5):
            raise serializers.ValidationError({"rating": _("Rating must be between 1 and 5.")})
        Booking = apps.get_model('bookings', 'Booking')
        today = timezone.localdate()
        has_started_stay = Booking.objects.filter(
            property=prop, tenant=user
        ).exclude(
            status__in=[BookingStatus.CANCELLED, BookingStatus.CANCELED]
        ).filter(
            start_date__lte=today
        ).exists()
        if not has_started_stay:
            raise serializers.ValidationError(_("You can leave a review only after your stay has started."))
        if Review.objects.filter(property=prop, author=user).exists():
            raise serializers.ValidationError(_("You have already reviewed this property."))
        return attrs

    def create(self, validated_data):
        validated_data["author"] = self.context["request"].user
        return super().create(validated_data)
