from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages

from rest_framework import viewsets, permissions
from rest_framework.exceptions import PermissionDenied

from src.properties.models import Property
from .models import Review
from .serializers import ReviewSerializer


def _first_existing_field(model_cls, candidates):
    field_names = {f.name for f in model_cls._meta.get_fields()}
    for name in candidates:
        if name in field_names:
            return name
    return None


def user_has_booking_for_property(user, prop):
    try:
        from src.bookings.models import Booking
    except Exception:
        return False
    field_names = {f.name for f in Booking._meta.get_fields()}
    qs = Booking.objects.all()
    if "property" in field_names:
        qs = qs.filter(property=prop)
    elif "property_id" in field_names:
        qs = qs.filter(property_id=prop.pk)
    user_field = _first_existing_field(Booking, (
        "user", "author", "client", "customer", "renter", "tenant", "guest", "booked_by", "created_by", "owner"
    ))
    if user_field:
        qs = qs.filter(**{user_field: user})
    return qs.exists()


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all().order_by("-id")
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    filterset_fields = ["property", "rating"]
    search_fields = ["text", "comment", "content", "body", "message", "review", "description"]
    ordering_fields = ["id", "rating", "created_at"]

    def perform_create(self, serializer):
        user = self.request.user
        if not user.is_authenticated:
            raise PermissionDenied("Login required")
        prop_id = self.request.data.get("property")
        if not prop_id:
            raise PermissionDenied("Property is required")
        try:
            prop = Property.objects.get(pk=int(prop_id))
        except Exception:
            raise PermissionDenied("Bad property id")
        if not user_has_booking_for_property(user, prop):
            raise PermissionDenied("Only clients with a booking can review")

        user_field = _first_existing_field(Review, ("author", "user", "owner", "created_by", "creator"))
        if not user_field:
            raise PermissionDenied("No user field on Review model")
        if Review.objects.filter(property=prop, **{user_field: user}).exists():
            raise PermissionDenied("You already reviewed this property")

        serializer.save(**{user_field: user})


@require_POST
def submit_review(request, pk):
    prop = get_object_or_404(Property, pk=pk)

    if not request.user.is_authenticated:
        messages.error(request, "Войдите, чтобы оставить отзыв.")
        return redirect("property_detail", pk=pk)

    if not user_has_booking_for_property(request.user, prop):
        messages.error(request, "Оставлять отзыв могут только клиенты с бронированием этого объекта.")
        return redirect("property_detail", pk=pk)

    try:
        rating = int(request.POST.get("rating", ""))
        if rating < 1 or rating > 5:
            raise ValueError
    except ValueError:
        messages.error(request, "Укажите рейтинг от 1 до 5.")
        return redirect("property_detail", pk=pk)

    text_value = (request.POST.get("text") or "").strip()
    if not text_value:
        messages.error(request, "Напишите комментарий.")
        return redirect("property_detail", pk=pk)

    user_field = _first_existing_field(Review, ("author", "user", "owner", "created_by", "creator"))
    if not user_field:
        messages.error(request, "Модель отзыва не содержит поля пользователя.")
        return redirect("property_detail", pk=pk)

    if Review.objects.filter(property=prop, **{user_field: request.user}).exists():
        messages.error(request, "Вы уже оставляли отзыв об этом объекте.")
        return redirect("property_detail", pk=pk)

    text_field = _first_existing_field(Review, ("text", "comment", "content", "body", "message", "review", "description"))
    if not text_field:
        messages.error(request, "Модель отзыва не содержит текстового поля.")
        return redirect("property_detail", pk=pk)

    review_kwargs = {
        "property": prop,
        "rating": rating,
        user_field: request.user,
        text_field: text_value,
    }

    Review.objects.create(**review_kwargs)
    messages.success(request, "Спасибо! Отзыв добавлен.")
    return redirect("property_detail", pk=pk)
