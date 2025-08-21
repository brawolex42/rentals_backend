from django.utils.deprecation import MiddlewareMixin
from django.apps import apps
from django.utils import timezone


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


def _client_ip(request):
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class EnsureSessionMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if not request.session.session_key:
            request.session.create()


class SearchQueryLoggingMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        SearchQuery = _get_model("SearchQuery")
        if not SearchQuery:
            return response

        q = request.GET.get("q")
        if not q:
            return response

        kwargs = {}
        if _has_field(SearchQuery, "query"):
            kwargs["query"] = q[:255]
        elif _has_field(SearchQuery, "q"):
            kwargs["q"] = q[:255]

        if _has_field(SearchQuery, "session_key"):
            kwargs["session_key"] = request.session.session_key or ""
        if _has_field(SearchQuery, "ip"):
            kwargs["ip"] = _client_ip(request)
        if _has_field(SearchQuery, "path"):
            kwargs["path"] = request.path[:255]
        if _has_field(SearchQuery, "user") and getattr(request, "user", None) and request.user.is_authenticated:
            kwargs["user"] = request.user
        if _has_field(SearchQuery, "created_at"):
            kwargs["created_at"] = timezone.now()

        if kwargs:
            try:
                SearchQuery.objects.create(**kwargs)
            except Exception:
                pass

        return response
