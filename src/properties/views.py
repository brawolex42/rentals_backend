from django.views.generic import TemplateView, DetailView
from django.db.models import Avg, Count, Prefetch
from rest_framework import viewsets, permissions, status, serializers
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
import re

from .models import Property
from .serializers import PropertySerializer
from .permissions import IsOwnerOrReadOnly

def user_has_booking_for_property(user, prop):
    if not user.is_authenticated:
        return False
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
    user_field = None
    for f in ("user", "author", "client", "customer", "renter", "tenant", "guest", "booked_by", "created_by", "owner"):
        if f in field_names:
            user_field = f
            break
    if user_field:
        qs = qs.filter(**{user_field: user})
    return qs.exists()

def _mask_email_like(s):
    if not s:
        return ""
    if "@" in s:
        local = s.split("@", 1)[0]
        if len(local) <= 2:
            return (local[:1] + "*" * max(len(local) - 1, 0)) or "User"
        return f"{local[0]}***{local[-1]}"
    return s

_email_re = re.compile(r"[\w\.\+\-]+@[\w\.-]+\.\w+", re.IGNORECASE)

def _sanitize_text(s):
    if not s:
        return s
    return _email_re.sub(lambda m: _mask_email_like(m.group(0)), s)

def _display_name_safe(u):
    if not u:
        return "User"
    try:
        dn = u.get_display_name()
        if dn:
            return _mask_email_like(dn)
    except Exception:
        pass
    first = (getattr(u, "first_name", "") or "").strip()
    last = (getattr(u, "last_name", "") or "").strip()
    if first or last:
        return _mask_email_like((first + " " + last).strip())
    username = (getattr(u, "username", "") or "").strip()
    if username:
        return _mask_email_like(username)
    return "User"

class PublicCatalogView(TemplateView):
    template_name = "properties/property_list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = (
            Property.objects.all()
            .annotate(
                rating_avg=Avg("reviews__rating"),
                reviews_total=Count("reviews", distinct=True),
            )
            .select_related("owner")
            .prefetch_related(Prefetch("images"))
            .order_by("-reviews_total", "-rating_avg", "-id")
        )
        props = list(qs)
        if props:
            prop_ids = [p.id for p in props]
            try:
                from src.bookings.models import Booking
            except Exception:
                for p in props:
                    p.user_booking = None
                    p.other_booking = False
                ctx["properties"] = props
                return ctx
            if self.request.user.is_authenticated:
                user_qs = (
                    Booking.objects.filter(tenant=self.request.user, property_id__in=prop_ids)
                    .exclude(status__in=["CANCELLED", "COMPLETED", "CANCELED"])
                    .order_by("property_id", "-created_at")
                )
                latest_by_prop = {}
                for b in user_qs:
                    if b.property_id not in latest_by_prop:
                        latest_by_prop[b.property_id] = b
                other_ids = set(
                    Booking.objects.filter(property_id__in=prop_ids)
                    .exclude(status__in=["CANCELLED", "COMPLETED", "CANCELED"])
                    .exclude(tenant=self.request.user)
                    .values_list("property_id", flat=True)
                )
                for p in props:
                    p.user_booking = latest_by_prop.get(p.id)
                    p.other_booking = p.id in other_ids
            else:
                other_ids = set(
                    Booking.objects.exclude(status__in=["CANCELLED", "COMPLETED", "CANCELED"]).values_list("property_id", flat=True)
                )
                for p in props:
                    p.user_booking = None
                    p.other_booking = p.id in other_ids
        ctx["properties"] = props
        return ctx

class PublicPropertyDetailView(DetailView):
    model = Property
    template_name = "properties/property_detail.html"
    context_object_name = "property"

    def get_queryset(self):
        return (
            Property.objects.all()
            .annotate(
                rating_avg=Avg("reviews__rating"),
                reviews_total=Count("reviews", distinct=True),
            )
            .select_related("owner")
            .prefetch_related(Prefetch("images"), Prefetch("reviews"))
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["user_can_review"] = user_has_booking_for_property(self.request.user, self.object)
        user_booking = None
        if self.request.user.is_authenticated:
            try:
                from src.bookings.models import Booking
                user_booking = (
                    Booking.objects.filter(property=self.object, tenant=self.request.user)
                    .exclude(status__in=["CANCELLED", "COMPLETED", "CANCELED"])
                    .order_by("-created_at")
                    .first()
                )
            except Exception:
                user_booking = None
        ctx["user_booking"] = user_booking
        raw_reviews = list(getattr(self.object, "reviews").all().select_related("author"))
        safe_reviews = []
        for r in raw_reviews:
            author = getattr(r, "author", None)
            safe_reviews.append(
                {
                    "id": r.id,
                    "rating": r.rating,
                    "text": _sanitize_text(r.text),
                    "created_at": r.created_at,
                    "display_user": _display_name_safe(author),
                }
            )
        ctx["reviews"] = safe_reviews
        return ctx

class PropertyViewSet(viewsets.ModelViewSet):
    queryset = (
        Property.objects.all()
        .annotate(
            rating_avg=Avg("reviews__rating"),
            reviews_total=Count("reviews", distinct=True),
        )
        .order_by("-id")
    )
    serializer_class = PropertySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    search_fields = ["title", "description", "city", "district"]
    ordering_fields = ["price", "created_at", "rating_avg", "reviews_total", "id"]

    def perform_create(self, serializer):
        try:
            serializer.save(owner=self.request.user)
        except TypeError:
            serializer.save()

class ContactPropertySerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=50, required=False, allow_blank=True)
    message = serializers.CharField(min_length=10, max_length=2000)

class ContactPropertyView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, pk: int):
        prop = get_object_or_404(Property.objects.select_related("owner"), pk=pk)
        s = ContactPropertySerializer(data=request.data)
        if not s.is_valid():
            return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)
        data = s.validated_data
        to_email = (prop.owner.email or "").strip()
        if not to_email:
            return Response({"detail": "No host email."}, status=400)
        ctx = {
            "property": prop,
            "name": data["name"],
            "email": data["email"],
            "phone": data.get("phone", ""),
            "message": data["message"],
        }
        subject = f"Inquiry: {prop.title} (#{prop.pk})"
        html = render_to_string("emails/inquiry.html", ctx)
        text = f"Property: {prop.title} (#{prop.pk})\nName: {ctx['name']}\nEmail: {ctx['email']}\nPhone: {ctx['phone']}\n\nMessage:\n{ctx['message']}"
        msg = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [to_email])
        msg.attach_alternative(html, "text/html")
        msg.reply_to = [ctx["email"]]
        msg.send()
        return Response({"detail": "Message sent."})
