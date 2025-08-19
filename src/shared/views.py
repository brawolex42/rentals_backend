from django.conf import settings
from django.http import HttpResponseRedirect
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme
from urllib.parse import urlsplit, urlunsplit

SESSION_LANG_KEY = "django_language"

def _normalize_path_for_lang(path, lang, default_lang, allowed_codes):
    if not path:
        path = "/"
    if not path.startswith("/"):
        path = "/" + path
    prefixes = {code: f"/{code}/" for code in allowed_codes}
    has_prefix = False
    current_code = None
    for code, pref in prefixes.items():
        if path == f"/{code}" or path.startswith(pref):
            has_prefix = True
            current_code = code
            break
    if lang == default_lang:
        if has_prefix and current_code != default_lang:
            pref = prefixes[current_code]
            if path == f"/{current_code}":
                path = "/"
            elif path.startswith(pref):
                path = path[len(pref)-1:]
        return path
    target_pref = prefixes[lang]
    if has_prefix:
        if current_code == lang:
            return path
        pref = prefixes[current_code]
        if path == f"/{current_code}":
            rest = "/"
        elif path.startswith(pref):
            rest = path[len(pref)-1:]
        else:
            rest = path
        if rest == "/":
            return target_pref
        if rest.startswith("/"):
            return target_pref[:-1] + rest
        return target_pref + rest
    if path == "/":
        return target_pref
    if path.startswith("/"):
        return target_pref[:-1] + path
    return target_pref + path

def setlang_get(request):
    lang = (request.GET.get("language") or "").lower().split("-")[0]
    nxt = request.GET.get("next") or "/"
    if not url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        nxt = "/"
    allowed = [code for code, _ in getattr(settings, "LANGUAGES", [])]
    default_lang = settings.LANGUAGE_CODE.split("-")[0]
    if lang not in allowed:
        lang = default_lang
    parts = urlsplit(nxt)
    new_path = _normalize_path_for_lang(parts.path, lang, default_lang, allowed)
    new_url = urlunsplit((parts.scheme, parts.netloc, new_path, parts.query, parts.fragment))
    response = HttpResponseRedirect(new_url or "/")
    if hasattr(request, "session"):
        request.session[SESSION_LANG_KEY] = lang
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME,
        lang,
        max_age=getattr(settings, "LANGUAGE_COOKIE_AGE", None),
        path=getattr(settings, "LANGUAGE_COOKIE_PATH", "/"),
        domain=getattr(settings, "LANGUAGE_COOKIE_DOMAIN", None),
        secure=getattr(settings, "LANGUAGE_COOKIE_SECURE", False),
        httponly=getattr(settings, "LANGUAGE_COOKIE_HTTPONLY", False),
        samesite=getattr(settings, "LANGUAGE_COOKIE_SAMESITE", "Lax"),
    )
    translation.activate(lang)
    request.LANGUAGE_CODE = lang
    return response
from django.conf import settings
from django.http import HttpResponseRedirect
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme
from urllib.parse import urlsplit, urlunsplit

SESSION_LANG_KEY = "django_language"

def _normalize_path_for_lang(path, lang, default_lang, allowed_codes):
    if not path:
        path = "/"
    if not path.startswith("/"):
        path = "/" + path
    prefixes = {code: f"/{code}/" for code in allowed_codes}
    has_prefix = False
    current_code = None
    for code, pref in prefixes.items():
        if path == f"/{code}" or path.startswith(pref):
            has_prefix = True
            current_code = code
            break
    if lang == default_lang:
        if has_prefix and current_code != default_lang:
            pref = prefixes[current_code]
            if path == f"/{current_code}":
                path = "/"
            elif path.startswith(pref):
                path = path[len(pref)-1:]
        return path
    target_pref = prefixes[lang]
    if has_prefix:
        if current_code == lang:
            return path
        pref = prefixes[current_code]
        if path == f"/{current_code}":
            rest = "/"
        elif path.startswith(pref):
            rest = path[len(pref)-1:]
        else:
            rest = path
        if rest == "/":
            return target_pref
        if rest.startswith("/"):
            return target_pref[:-1] + rest
        return target_pref + rest
    if path == "/":
        return target_pref
    if path.startswith("/"):
        return target_pref[:-1] + path
    return target_pref + path

def setlang_get(request):
    lang = (request.GET.get("language") or "").lower().split("-")[0]
    nxt = request.GET.get("next") or "/"
    if not url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        nxt = "/"
    allowed = [code for code, _ in getattr(settings, "LANGUAGES", [])]
    default_lang = settings.LANGUAGE_CODE.split("-")[0]
    if lang not in allowed:
        lang = default_lang
    parts = urlsplit(nxt)
    new_path = _normalize_path_for_lang(parts.path, lang, default_lang, allowed)
    new_url = urlunsplit((parts.scheme, parts.netloc, new_path, parts.query, parts.fragment))
    response = HttpResponseRedirect(new_url or "/")
    if hasattr(request, "session"):
        request.session[SESSION_LANG_KEY] = lang
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME,
        lang,
        max_age=getattr(settings, "LANGUAGE_COOKIE_AGE", None),
        path=getattr(settings, "LANGUAGE_COOKIE_PATH", "/"),
        domain=getattr(settings, "LANGUAGE_COOKIE_DOMAIN", None),
        secure=getattr(settings, "LANGUAGE_COOKIE_SECURE", False),
        httponly=getattr(settings, "LANGUAGE_COOKIE_HTTPONLY", False),
        samesite=getattr(settings, "LANGUAGE_COOKIE_SAMESITE", "Lax"),
    )
    translation.activate(lang)
    request.LANGUAGE_CODE = lang
    return response
