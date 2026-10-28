FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# DEV=1 also installs the test and lint tools
ARG DEV=0

WORKDIR /app

# GNU gettext compiles the translations (locale/*.po) at build time.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gettext \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-dev.txt ./
RUN if [ "$DEV" = "1" ]; then pip install -r requirements-dev.txt; else pip install -r requirements.txt; fi

COPY . .

RUN useradd --create-home --uid 1000 app \
    && DJANGO_SECRET_KEY=build-only python manage.py collectstatic --noinput \
    && DJANGO_SECRET_KEY=build-only python manage.py compilemessages --ignore=".venv" \
    && chown -R app:app /app
USER app

EXPOSE 8000

# 2 processes (the e2-micro has 1 GB) with 4 threads each: a slow request does not hold up
# the whole site.
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --threads 4"]
