import socket

from .base import *  # noqa: F401,F403

DEBUG = True
DEMO_MODE = True
ALLOWED_HOSTS = env_list(  # noqa: F405
    "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1],0.0.0.0,testserver"
)
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
INTERNAL_IPS = ["127.0.0.1", "::1"]
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False


def _can_connect(host: str, port: int | str, timeout: float = 0.2) -> bool:
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except OSError:
        return False


# Automatic fallback for local development if Postgres/Redis services are not running
db_host = env("DB_HOST", "127.0.0.1")  # noqa: F405
db_port = env("DB_PORT", "5432")  # noqa: F405
if env("DB_ENGINE", None) is None:  # noqa: F405
    if not _can_connect(db_host, db_port):
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
            }
        }

if not _can_connect("127.0.0.1", 6379):
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "linee-dev-cache",
        }
    }
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
