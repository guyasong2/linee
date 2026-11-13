# syntax=docker/dockerfile:1
FROM node:24-alpine AS assets
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY tailwind.config.js ./
COPY static ./static
COPY templates ./templates
COPY apps ./apps
RUN npm run build

FROM python:3.13-slim AS python-build
COPY --from=ghcr.io/astral-sh/uv:0.12.21 /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
COPY --from=assets /app/static ./static
RUN uv sync --frozen --no-dev
RUN DJANGO_SETTINGS_MODULE=config.settings.build .venv/bin/python manage.py collectstatic --noinput

FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod
RUN addgroup --system app && adduser --system --ingroup app app
WORKDIR /app
COPY --from=python-build /app /app
RUN chown -R app:app /app
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live/', timeout=3)" || exit 1
CMD ["/app/.venv/bin/daphne", "-b", "0.0.0.0", "-p", "8000", "config.asgi:application"]
