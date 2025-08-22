from django.utils import translation
from django.conf import settings

class QueryStringLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        lang = request.GET.get("lang")
        if lang:
            translation.activate(lang)
            request.LANGUAGE_CODE = lang
        response = self.get_response(request)
        if lang:
            max_age = getattr(settings, "LANGUAGE_COOKIE_AGE", 31536000)
            name = getattr(settings, "LANGUAGE_COOKIE_NAME", "django_language")
            path = getattr(settings, "LANGUAGE_COOKIE_PATH", "/")
            samesite = getattr(settings, "LANGUAGE_COOKIE_SAMESITE", "Lax")
            response.set_cookie(name, lang, max_age=max_age, path=path, samesite=samesite)
        return response
