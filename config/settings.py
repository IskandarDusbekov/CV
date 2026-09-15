"""
Django settings for mycv.uz CV Builder project.

Barcha maxfiy va muhitga bog'liq qiymatlar .env dan o'qiladi (namuna: .env.example).
Biznes sozlamalari (karta raqami, narxlar, limitlar, AI modeli) — admin panel → "Sayt sozlamalari".
"""
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass


def _env(key, default=None):
    return os.environ.get(key, default)


def _env_bool(key, default=False):
    val = os.environ.get(key, "")
    if val == "":
        return default
    return val.lower() in ("1", "true", "yes", "on")


def _env_list(key, default=""):
    """Vergul bilan ajratilgan env qiymatini ro'yxatga aylantiradi. default — matn yoki ro'yxat."""
    raw = os.environ.get(key)
    if raw is None:
        if isinstance(default, (list, tuple)):
            return [str(v).strip() for v in default if str(v).strip()]
        raw = default
    return [v.strip() for v in raw.split(",") if v.strip()]


# ── Security ────────────────────────────────────────────────────────────────
DEBUG = _env_bool("DEBUG", default=True)

_INSECURE_KEY = "django-insecure-change-me-before-deploying-to-production-mycvuz"
SECRET_KEY = _env("SECRET_KEY", _INSECURE_KEY)
if not DEBUG and SECRET_KEY == _INSECURE_KEY:
    raise ImproperlyConfigured("Productionda SECRET_KEY ni .env da o'rnating (DEBUG=False).")

ALLOWED_HOSTS = _env_list(
    "DJANGO_ALLOWED_HOSTS",
    ["postbox-cargo-reawake.ngrok-free.dev", "127.0.0.1", "localhost"],
)
CSRF_TRUSTED_ORIGINS = _env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    ["https://postbox-cargo-reawake.ngrok-free.dev"],
)

if not DEBUG:
    # Nginx HTTPS ni o'zi tugatadi va X-Forwarded-Proto yuboradi
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = _env_bool("SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(_env("SECURE_HSTS_SECONDS", "0"))  # SSL ishlashiga ishonch hosil qilgach 31536000
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"

# ── Application definition ───────────────────────────────────────────────────
INSTALLED_APPS = [
    "jazzmin",  # django.contrib.admin dan oldin bo'lishi shart

    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "corsheaders",
    "import_export",

    "apps.core",
    "apps.users",
    "apps.cv",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.activity.BlockAndPresenceMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ── Database ─────────────────────────────────────────────────────────────────
# DB_ENGINE=postgres bo'lsa PostgreSQL, aks holda SQLite
if _env("DB_ENGINE", "sqlite").lower() in ("postgres", "postgresql"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _env("DB_NAME", "mycv"),
            "USER": _env("DB_USER", "mycv"),
            "PASSWORD": _env("DB_PASSWORD", ""),
            "HOST": _env("DB_HOST", "127.0.0.1"),
            "PORT": _env("DB_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "uz"
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

# ── Static & media ────────────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        # Manifest (hash) storage Jazzmin dagi yo'q .map fayllar sababli collectstatic da yiqiladi
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage" if not DEBUG
        else "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/users/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

SESSION_COOKIE_AGE = 60 * 60 * 24 * 30
SESSION_SAVE_EVERY_REQUEST = False

CORS_ALLOWED_ORIGINS = _env_list("CORS_ALLOWED_ORIGINS", default="http://localhost:8000,http://127.0.0.1:8000")
CORS_ALLOW_CREDENTIALS = True

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
if "test" in __import__("sys").argv:
    # testlarda DB har safar tozalanadi — sozlamalar keshi eskirib qolmasin
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}

# ── Tashqi servislar ──────────────────────────────────────────────────────────
OPENAI_API_KEY = _env("OPENAI_API_KEY", "")
SITE_URL = _env("SITE_URL", "http://127.0.0.1:8000")
TELEGRAM_BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_BOT_USERNAME = _env("TELEGRAM_BOT_USERNAME", "")

# Click (ulanganda). Hozircha to'lovlar bot orqali qabul qilinadi.
CLICK_SERVICE_ID = _env("CLICK_SERVICE_ID", "")
CLICK_MERCHANT_ID = _env("CLICK_MERCHANT_ID", "")

# ── Jazzmin admin ─────────────────────────────────────────────────────────────
JAZZMIN_SETTINGS = {
    "site_title": "mycv.uz admin",
    "site_header": "mycv.uz",
    "site_brand": "mycv.uz",
    "welcome_sign": "mycv.uz boshqaruv paneli",
    "copyright": "mycv.uz",
    "show_sidebar": True,
    "navigation_expanded": True,
    "topmenu_links": [
        {"name": "Bosh sahifa", "url": "admin:index"},
        {"name": "Saytni ochish", "url": "/", "new_window": True},
        {"name": "💳 Tekshirish kerak", "url": "/admin/users/paymentrequest/?status__exact=pending"},
    ],
    "order_with_respect_to": [
        "users.paymentrequest", "users.userprofile", "cv.cv", "cv.aiusage", "core.activitylog", "core.errorlog",
        "users.pricingplan", "core.sitesettings", "core.page", "core.contactmessage", "core.blockedip",
    ],
    "hide_models": ["users.telegramlogintoken", "users.paymenttransaction", "users.usersubscription", "auth.group"],
    "icons": {
        "users.paymentrequest": "fas fa-receipt",
        "users.userprofile": "fas fa-users",
        "users.pricingplan": "fas fa-tags",
        "cv.cv": "fas fa-file-alt",
        "cv.aiusage": "fas fa-robot",
        "core.activitylog": "fas fa-history",
        "core.errorlog": "fas fa-bug",
        "core.sitesettings": "fas fa-cog",
        "core.page": "fas fa-file",
        "core.contactmessage": "fas fa-envelope",
        "core.blockedip": "fas fa-ban",
        "auth.user": "fas fa-user-shield",
        "users.companybranding": "fas fa-building",
    },
}

# ── Logging ───────────────────────────────────────────────────────────────────
# ERROR darajadagi hamma narsa admin paneldagi "Xatoliklar" bo'limiga ham yoziladi
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "{levelname} {asctime} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
        "database": {"class": "apps.core.activity.DatabaseErrorHandler", "level": "ERROR"},
    },
    "root": {"handlers": ["console", "database"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": _env("DJANGO_LOG_LEVEL", "INFO"), "propagate": False},
        "django.request": {"handlers": ["console", "database"], "level": "ERROR", "propagate": False},
        "apps": {"handlers": ["console", "database"], "level": "INFO", "propagate": False},
        "telegram_bot": {"handlers": ["console", "database"], "level": "INFO", "propagate": False},
        "httpx": {"level": "WARNING"},
    },
}
