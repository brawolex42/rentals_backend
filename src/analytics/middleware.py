from typing import Callable
from django.http import HttpRequest, HttpResponse
from .models import SearchQuery

class SearchQueryLoggingMiddleware:
    """
    Логирует ключевое слово (?search=...) при GET /api/properties/
    """
    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if (
            request.method == "GET"
            and request.path.startswith("/api/properties/")
        ):
            q = request.GET.get("search")
            if q:
                user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
                # режем до 255, как в модели
                SearchQuery.objects.create(user=user, query=q[:255])
        return self.get_response(request)
