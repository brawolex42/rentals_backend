from datetime import timedelta
import re

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Avg, Count, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.generic import TemplateView, DetailView

from django.contrib.auth import get_user_model

from rest_framework import viewsets, permissions, status, serializers
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters as drf_filters

from .models import Property
from .serializers import PropertySerializer
from .permissions import IsOwnerOrReadOnly
from .filters import PropertyFilter

try:
    from src.analytics.models import ViewEvent
    HAS_ANALYTICS = True
except Exception:
    ViewEvent = None
    HAS_ANALYTICS = False


def _field_exists(model, name):
    return any(f.name == name for f in model._meta.get_fields())


def _detect_type_field():
    for n in ("property_type", "type", "kind", "category"):
        if _field_exists(Property, n):
            return n
    return None


def _ensure_session_key(request):
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key


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
        dn = u.get_full_name()
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
    email = (getattr(u, "email", "") or "").strip()
    if email:
        return _mask_email_like(email)
    return "User"


def user_has_booking_for_property(user, prop):
    if not getattr(user, "is_authenticated", False):
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
    for f in ("user", "author", "client", "customer", "tenant", "renter", "guest", "booked_by", "created_by"):
        if f in field_names:
            user_field = f
            break
    if user_field:
        qs = qs.filter(**{user_field: user})
    if "status" in field_names:
        qs = qs.exclude(status__in=["CANCELLED", "COMPLETED", "CANCELED"])
    return qs.exists()


def _get_admin_contact():
    email = getattr(settings, "ADMIN_CONTACT_EMAIL", "") or ""
    phone = getattr(settings, "ADMIN_CONTACT_PHONE", "") or ""
    if not email:
        try:
            U = get_user_model()
            admin = U.objects.filter(is_superuser=True).order_by("id").first()
            if admin and admin.email:
                email = admin.email
        except Exception:
            pass
    return {"email": email, "phone": phone}


class PublicCatalogView(TemplateView):
    template_name = "properties/property_list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        q = (self.request.GET.get("q") or "").strip()
        city = (self.request.GET.get("city") or "").strip()
        ptype = (self.request.GET.get("ptype") or "").strip()
        sort = (self.request.GET.get("sort") or "").strip()
        postal = (self.request.GET.get("postal") or "").strip()
        address = (self.request.GET.get("address") or "").strip()
        type_field = _detect_type_field()

        qs = Property.objects.all().annotate(
            rating_avg=Avg("reviews__rating"),
            reviews_total=Count("reviews", distinct=True),
        ).select_related("owner").prefetch_related(Prefetch("images"))

        if HAS_ANALYTICS:
            week_ago = timezone.now() - timedelta(days=7)
            qs = qs.annotate(
                views_total=Count("view_events", distinct=True),
                views_7d=Count("view_events", filter=Q(view_events__created_at__gte=week_ago), distinct=True),
            )

        if q:
            qs = qs.filter(
                Q(title__icontains=q)
                | Q(description__icontains=q)
                | Q(city__icontains=q)
                | Q(district__icontains=q)
                | Q(address_line__icontains=q)
                | Q(postal_code__icontains=q)
            )
        if address:
            qs = qs.filter(address_line__icontains=address)
        if postal:
            qs = qs.filter(postal_code__iexact=postal)
        if city:
            qs = qs.filter(city__iexact=city)
        if ptype and type_field:
            qs = qs.filter(**{f"{type_field}__iexact": ptype})

        if sort == "views7" and HAS_ANALYTICS:
            qs = qs.order_by("-views_7d", "-id")
        elif sort == "views" and HAS_ANALYTICS:
            qs = qs.order_by("-views_total", "-id")
        else:
            qs = qs.order_by("-reviews_total", "-rating_avg", "-id")

        paginator = Paginator(qs, 12)
        page = self.request.GET.get("page") or 1
        try:
            page_obj = paginator.page(page)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        cities = list(
            Property.objects.exclude(city__isnull=True, city__exact="")
            .values_list("city", flat=True).distinct().order_by("city")
        )

        ptypes = []
        if type_field:
            field = Property._meta.get_field(type_field)
            if getattr(field, "choices", None):
                ptypes = [c[0] for c in field.choices if c and c[0]]
            else:
                ptypes = list(
                    Property.objects.exclude(**{f"{type_field}__isnull": True})
                    .exclude(**{f"{type_field}__exact": ""})
                    .values_list(type_field, flat=True).distinct().order_by(type_field)
                )

        ctx.update({
            "page_obj": page_obj,
            "properties": list(page_obj.object_list),
            "q": q, "city": city, "ptype": ptype, "sort": sort,
            "postal": postal, "address": address,
            "cities": cities, "ptypes": ptypes, "type_field": type_field,
            "admin_contact": _get_admin_contact(),
        })
        return ctx


class PublicPropertyDetailView(DetailView):
    model = Property
    template_name = "properties/property_detail.html"
    context_object_name = "property"

    def get_queryset(self):
        return (
            Property.objects.all()
            .annotate(rating_avg=Avg("reviews__rating"), reviews_total=Count("reviews", distinct=True))
            .select_related("owner")
            .prefetch_related(Prefetch("images"), Prefetch("reviews"))
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if HAS_ANALYTICS and ViewEvent:
            try:
                session_key = _ensure_session_key(self.request)
                ip = self.request.META.get("REMOTE_ADDR", "")[:64]
                ua = self.request.META.get("HTTP_USER_AGENT", "")[:500]
                ref = self.request.META.get("HTTP_REFERER", "")[:1000]
                ViewEvent.objects.create(
                    property=self.object,
                    user=self.request.user if getattr(self.request.user, "is_authenticated", False) else None,
                    session_key=session_key,
                    ip=ip,
                    user_agent=ua,
                    referer=ref,
                )
                week_ago = timezone.now() - timedelta(days=7)
                ctx["views_count"] = ViewEvent.objects.filter(property=self.object, created_at__gte=week_ago).count()
                ctx["views_total"] = ViewEvent.objects.filter(property=self.object).count()
            except Exception:
                ctx["views_count"] = 0
                ctx["views_total"] = 0
        else:
            ctx["views_count"] = 0
            ctx["views_total"] = 0

        raw_reviews = list(getattr(self.object, "reviews").all().select_related("author"))
        safe_reviews = []
        for r in raw_reviews:
            author = getattr(r, "author", None)
            safe_reviews.append(
                {
                    "id": r.id,
                    "rating": r.rating,
                    "text": _sanitize_text(getattr(r, "text", "")),
                    "created_at": r.created_at,
                    "display_user": _display_name_safe(author),
                }
            )
        ctx["reviews"] = safe_reviews
        ctx["user_can_review"] = user_has_booking_for_property(self.request.user, self.object)

        user_booking = None
        if getattr(self.request.user, "is_authenticated", False):
            try:
                from src.bookings.models import Booking
                user_booking = (
                    Booking.objects.filter(property=self.object)
                    .filter(Q(tenant=self.request.user) | Q(user=self.request.user) | Q(client=self.request.user))
                    .exclude(status__in=["CANCELLED", "COMPLETED", "CANCELED"])
                    .order_by("-created_at")
                    .first()
                )
            except Exception:
                user_booking = None
        ctx["user_booking"] = user_booking
        ctx["admin_contact"] = _get_admin_contact()
        return ctx


class PropertyViewSet(viewsets.ModelViewSet):
    queryset = (
        Property.objects.all()
        .annotate(rating_avg=Avg("reviews__rating"), reviews_total=Count("reviews", distinct=True))
        .order_by("-id")
    )
    serializer_class = PropertySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOwnerOrReadOnly]
    filter_backends = (DjangoFilterBackend, drf_filters.SearchFilter, drf_filters.OrderingFilter)
    filterset_class = PropertyFilter
    search_fields = ["title", "description", "city", "district", "address_line", "postal_code"]
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
