from config.env import env, env_bool, env_int, env_list

from .base import *  # noqa: F401,F403

DEBUG = False
DEMO_MODE = env_bool("DEMO_MODE", False)  # noqa: F405
SECRET_KEY = env("DJANGO_SECRET_KEY", required=True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", required=True)
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "")

DATABASES["default"]["CONN_MAX_AGE"] = env_int("DB_CONN_MAX_AGE", 60)  # noqa: F405

# Vercel serverless functions cannot host a Celery worker; run tasks inline
# unless a separate worker is provisioned elsewhere.
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", False)  # noqa: F405

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
SECURE_SSL_REDIRECT = True
SECURE_REDIRECT_EXEMPT = [r"^health/live/$", r"^health/ready/$"]
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_REFERRER_POLICY = "same-origin"
