from django.apps import apps
from django.utils import timezone
from django.db.models import Count
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView


def _get_model(name: str):
    try:
        return apps.get_model(apps.get_app_config("analytics").label, name)
    except Exception:
        return None


def _has_field(model, name: str) -> bool:
    try:
        model._meta.get_field(name)
        return True
    except Exception:
        return False


def _ensure_session(request):
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key or ""


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    return xff.split(",")[0].strip() if xff else request.META.get("REMOTE_ADDR", "")


SearchQuery = _get_model("SearchQuery")
ViewEvent = _get_model("ViewEvent")


class PopularSearchesView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        if not SearchQuery:
            return Response([])
        q_field = "query" if _has_field(SearchQuery, "query") else ("q" if _has_field(SearchQuery, "q") else None)
        if not q_field:
            return Response([])
        qs = SearchQuery.objects.all()
        if _has_field(SearchQuery, "created_at"):
            qs = qs.filter(created_at__gte=timezone.now() - timezone.timedelta(days=30))
        elif _has_field(SearchQuery, "timestamp"):
            qs = qs.filter(timestamp__gte=timezone.now() - timezone.timedelta(days=30))
        rows = (
            qs.values(q_field)
            .annotate(count=Count("id"))
            .order_by("-count")[:20]
        )
        data = [{"query": r[q_field], "count": r["count"]} for r in rows if r[q_field]]
        return Response(data)


class MySearchHistoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not SearchQuery:
            return Response([])
        q_field = "query" if _has_field(SearchQuery, "query") else ("q" if _has_field(SearchQuery, "q") else None)
        if not q_field:
            return Response([])
        qs = SearchQuery.objects.all()
        if _has_field(SearchQuery, "user"):
            qs = qs.filter(user=request.user)
        elif _has_field(SearchQuery, "session_key"):
            qs = qs.filter(session_key=_ensure_session(request))
        elif _has_field(SearchQuery, "ip"):
            qs = qs.filter(ip=_client_ip(request))
        if _has_field(SearchQuery, "created_at"):
            qs = qs.order_by("-created_at")
        elif _has_field(SearchQuery, "timestamp"):
            qs = qs.order_by("-timestamp")
        else:
            qs = qs.order_by("-id")
        qs = qs[:100]
        data = []
        for r in qs:
            item = {"query": getattr(r, q_field, ""), "id": r.pk}
            if _has_field(SearchQuery, "created_at"):
                item["created_at"] = getattr(r, "created_at", None)
            elif _has_field(SearchQuery, "timestamp"):
                item["created_at"] = getattr(r, "timestamp", None)
            data.append(item)
        return Response(data)


class MyViewHistoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not ViewEvent:
            return Response([])
        qs = ViewEvent.objects.all()
        if _has_field(ViewEvent, "user"):
            qs = qs.filter(user=request.user)
        elif _has_field(ViewEvent, "session_key"):
            qs = qs.filter(session_key=_ensure_session(request))
        if hasattr(qs, "select_related") and _has_field(ViewEvent, "property"):
            qs = qs.select_related("property")
        if _has_field(ViewEvent, "created_at"):
            qs = qs.order_by("-created_at")
        else:
            qs = qs.order_by("-id")
        qs = qs[:200]
        out = []
        for ev in qs:
            item = {"id": ev.pk}
            if _has_field(ViewEvent, "created_at"):
                item["created_at"] = getattr(ev, "created_at", None)
            if _has_field(ViewEvent, "path"):
                item["path"] = getattr(ev, "path", "")
            if _has_field(ViewEvent, "url"):
                item["url"] = getattr(ev, "url", "")
            if _has_field(ViewEvent, "property"):
                p = getattr(ev, "property", None)
                if p:
                    item["property"] = {
                        "id": getattr(p, "id", None),
                        "title": getattr(p, "title", "") or getattr(p, "name", ""),
                        "city": getattr(p, "city", ""),
                    }
            out.append(item)
        return Response(out)


class SearchQueryList(generics.ListAPIView):
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        if SearchQuery:
            qs = SearchQuery.objects
            return qs.order_by("-id")[:200]
        return []

    def list(self, request, *args, **kwargs):
        if not SearchQuery:
            return Response([])
        rows = self.get_queryset()
        q_field = "query" if _has_field(SearchQuery, "query") else ("q" if _has_field(SearchQuery, "q") else None)
        data = []
        for r in rows:
            data.append({
                "id": r.pk,
                "query": getattr(r, q_field, "") if q_field else "",
                "created_at": getattr(r, "created_at", None) if _has_field(SearchQuery, "created_at") else getattr(r, "timestamp", None),
            })
        return Response(data)


class ViewEventList(generics.ListAPIView):
    permission_classes = [permissions.IsAdminUser]

    def get_queryset(self):
        if ViewEvent:
            qs = ViewEvent.objects
            if hasattr(qs, "select_related") and _has_field(ViewEvent, "property"):
                qs = qs.select_related("property")
            return qs.order_by("-id")[:200]
        return []

    def list(self, request, *args, **kwargs):
        if not ViewEvent:
            return Response([])
        rows = self.get_queryset()
        data = []
        for ev in rows:
            item = {"id": ev.pk}
            if _has_field(ViewEvent, "created_at"):
                item["created_at"] = getattr(ev, "created_at", None)
            if _has_field(ViewEvent, "path"):
                item["path"] = getattr(ev, "path", "")
            if _has_field(ViewEvent, "url"):
                item["url"] = getattr(ev, "url", "")
            if _has_field(ViewEvent, "property"):
                p = getattr(ev, "property", None)
                if p:
                    item["property"] = {
                        "id": getattr(p, "id", None),
                        "title": getattr(p, "title", "") or getattr(p, "name", ""),
                        "city": getattr(p, "city", ""),
                    }
            data.append(item)
        return Response(data)
