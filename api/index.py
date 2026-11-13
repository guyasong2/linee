"""Vercel serverless entrypoint for the Django app."""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")
os.environ.setdefault("LINE_SKIP_DOTENV", "1")

from django.core.wsgi import get_wsgi_application

app = get_wsgi_application()
