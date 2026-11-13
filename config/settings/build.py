from .base import *  # noqa: F401,F403

# Used only by collectstatic inside the container image build.
DEBUG = False
SECRET_KEY = "build-only-not-a-runtime-secret"
ALLOWED_HOSTS = ["localhost"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}
