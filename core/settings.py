from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env", override=False)
load_dotenv(BASE_DIR / ".env.local", override=True)

def as_bool(v: str, default=False) -> bool:
    if v is None:
        return default
    return str(v).strip().lower() in {"1", "true", "yes", "y", "on"}

def as_list(v: str, sep=","):
    if not v:
        return []
    return [x.strip() for x in str(v).split(sep) if x.strip()]

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
DEBUG = as_bool(os.getenv("DEBUG", "true"), default=True)
ALLOWED_HOSTS = as_list(os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost"))

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "rest_framework_simplejwt",
    "src.accounts.apps.AccountsConfig",
    "src.properties.apps.PropertiesConfig",
    "src.bookings.apps.BookingsConfig",
    "src.reviews.apps.ReviewsConfig",
    "src.analytics.apps.AnalyticsConfig",
    "src.shared.apps.SharedConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "src.analytics.middleware.EnsureSessionMiddleware",
    "src.analytics.middleware.SearchQueryLoggingMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

USE_WHITENOISE = as_bool(os.getenv("USE_WHITENOISE", "false"))
if USE_WHITENOISE:
    try:
        import whitenoise  # noqa: F401
        MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
    except Exception:
        USE_WHITENOISE = False

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates", BASE_DIR / "src" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "src.shared.context_processors.admin_contact",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"

AUTH_USER_MODEL = "accounts.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_PAGINATION_CLASS": "src.shared.pagination.DefaultPagination",
    "PAGE_SIZE": 20,
}

IS_DOCKER = os.path.exists("/.dockerenv") or os.getenv("IN_DOCKER") == "1"

if as_bool(os.getenv("DB_USE_SQLITE", "false")):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    env_db_host = os.getenv("DB_HOST", None)
    env_db_port = os.getenv("DB_PORT", "3306")
    default_host = "db" if IS_DOCKER else "127.0.0.1"
    if (not IS_DOCKER) and (env_db_host is None or env_db_host.strip().lower() == "db"):
        resolved_host = "127.0.0.1"
    else:
        resolved_host = env_db_host.strip() if env_db_host else default_host

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv("DB_NAME", "rentals"),
            "USER": os.getenv("DB_USER", "rentals"),
            "PASSWORD": os.getenv("DB_PASSWORD", "rentals123"),
            "HOST": resolved_host,
            "PORT": env_db_port,
            "OPTIONS": {
                "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
                "charset": "utf8mb4",
            },
        }
    }

LANGUAGE_CODE = "de"
LANGUAGES = [
    ("de", "Deutsch"),
    ("en", "English"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
LANGUAGE_COOKIE_NAME = "django_language"
LANGUAGE_COOKIE_AGE = 60 * 60 * 24 * 365
LANGUAGE_COOKIE_SAMESITE = "Lax"
LANGUAGE_COOKIE_PATH = "/"

TIME_ZONE = "Europe/Berlin"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static", BASE_DIR / "src" / "shared"]
STATIC_ROOT = BASE_DIR / "staticfiles"
if USE_WHITENOISE and not DEBUG:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = as_bool(os.getenv("EMAIL_USE_TLS", "true"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER or "no-reply@example.com"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/account/"
LOGOUT_REDIRECT_URL = "/"
