"""Kaladrius settings.

All sensitive or per-environment values come from environment variables (.env).
"""

import os
from pathlib import Path

from django.contrib.messages import constants as messages
from django.core.exceptions import ImproperlyConfigured
from django.utils.csp import CSP

# Name shown to users (decisions 060 and 068). Google Cloud names that cannot be renamed
# (project, backup bucket, network, identity provider) keep "medical-system" (decision 071).
NOME_SISTEMA = "Kaladrius"

BASE_DIR = Path(__file__).resolve().parent.parent


def env(nome, padrao=None):
    valor = os.environ.get(nome, padrao)
    if valor is None:
        raise ImproperlyConfigured(f"Missing required environment variable: {nome}")
    return valor


def env_bool(nome, padrao=False):
    return env(nome, "1" if padrao else "0").strip().lower() in {"1", "true", "sim", "yes"}


def env_lista(nome, padrao=""):
    return [item.strip() for item in env(nome, padrao).split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG")
# Production servers run daily backups (deploy/servidor/backup.sh): superusers are warned
# when none was recorded recently, or none at all. Development has no backups.
BACKUP_MONITORADO = env_bool("DJANGO_BACKUP_MONITORADO", padrao=not DEBUG)
# Health samples written every 5 minutes by deploy/servidor/saude.sh (decision 056):
# superusers are warned when they stop or a resource is critical.
SAUDE_MONITORADA = env_bool("DJANGO_SAUDE_MONITORADA", padrao=not DEBUG)
SAUDE_DIR = env("DJANGO_SAUDE_DIR", "/saude")
# The documentation site (docs/, decision 073): the Help menu links to it, in the user's
# language. Every installation links to the official site, which documents the newest version.
DOCS_URL = env("DJANGO_DOCS_URL", "https://docs.kaladrius.duckdns.org")
SECRET_KEY = env("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env_lista("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_lista("DJANGO_CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "apps.core",
    "apps.novidades",
    "apps.profissionais",
    "apps.referencias",
    "apps.agenda",
    "apps.pacientes",
    "apps.rechamadas",
    "apps.auditoria",
    "apps.equipe",
    "apps.legado",
    "apps.ajuda",
    "apps.financeiro",
    "apps.orcamentos",
    "apps.odontologia",
    "apps.monitoramento",
    # Serves the API docs page's own files (no CDN, which the CSP would block).
    "ninja",
    "axes",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # Language: the browser's (Accept-Language) before login; the user's choice after.
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.middleware.IdiomaDoUsuarioMiddleware",
    "apps.core.middleware.ClinicaAtualMiddleware",
    "apps.auditoria.middleware.AuditoriaMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Must be the last middleware (django-axes).
    "axes.middleware.AxesMiddleware",
]

# Behind Caddy in production: take the client IP from X-Forwarded-For (must run first).
if env_bool("DJANGO_PROXY_REVERSO"):
    MIDDLEWARE.insert(0, "apps.core.middleware.ProxyReversoMiddleware")

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.novidades.context_processors.versao",
                "apps.core.context_processors.clinica",
                "apps.core.context_processors.backup",
                "apps.monitoramento.context_processors.alerta",
                "apps.core.context_processors.idiomas",
                "apps.ajuda.context_processors.documentacao",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "kaladrius"),
        "USER": env("POSTGRES_USER", "kaladrius"),
        "PASSWORD": env("POSTGRES_PASSWORD", ""),
        "HOST": env("POSTGRES_HOST", "localhost"),
        "PORT": env("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}

AUTH_USER_MODEL = "core.Usuario"

# django-axes must be the first backend so it can block locked-out logins.
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# Brute-force protection: 5 wrong passwords for the same user from the same IP (for IPv6,
# the same /48 network) lock that combination for 1 hour. A successful login resets the
# counter.
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # hours
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
# IPv6 clients are grouped by /48 network, so rotating addresses does not reset the count.
AXES_CLIENT_IP_CALLABLE = "apps.core.seguranca.ip_para_bloqueio"
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = "registration/bloqueado.html"

# Argon2 first: new passwords use Argon2; others are upgraded on the next login.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "inicio"
LOGOUT_REDIRECT_URL = "login"

# The source texts are written in Portuguese; locale/ holds the English and Spanish
# translations (decision 049).
LANGUAGE_CODE = "pt-br"
LANGUAGES = [
    ("pt-br", "Português"),
    ("en", "English"),
    ("es", "Español"),
]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}

# In development, static files are served straight from the source folders (no collectstatic)
WHITENOISE_USE_FINDERS = DEBUG
WHITENOISE_AUTOREFRESH = DEBUG

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Django's "error" message level maps to Bootstrap's "danger" alert style
MESSAGE_TAGS = {messages.ERROR: "danger"}

# Version history file (What's new page, API and footer)
RELEASES_ARQUIVO = BASE_DIR / "releases.yaml"

# Session: expires after 8 hours and when the browser closes
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_HTTPONLY = True

# Protections that require HTTPS: enabled in production with DJANGO_SECURE=1
if env_bool("DJANGO_SECURE"):
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    LANGUAGE_COOKIE_SECURE = True

# Content-Security-Policy: scripts only from our own files (no inline scripts or event
# handlers in the templates; a test checks it), so injected HTML cannot run code. Inline
# styles stay allowed: FullCalendar and HTMX add them, and they cannot run code.
SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF],
    "style-src": [CSP.SELF, CSP.UNSAFE_INLINE],
    "img-src": [CSP.SELF, "data:"],  # Bootstrap draws some icons as data: SVGs
    "font-src": [CSP.SELF, "data:"],  # FullCalendar's arrow icons are a data: font
    "object-src": [CSP.NONE],
    "base-uri": [CSP.SELF],
    "form-action": [CSP.SELF],
    "frame-ancestors": [CSP.NONE],
}

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
