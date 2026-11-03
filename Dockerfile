# The Python of .python-version (decision 127; tests/test_python_version.py checks they agree),
# pinned by digest so the base image only changes in a reviewed commit; Dependabot proposes the
# new digest when the image is rebuilt (decision 138).
FROM python:3.14-slim@sha256:cd89c30eda26ee911a4611b18680086e0ea42e6f5f8cbe653d07fa7958c9cec8

# Shown on the package page and used by GitHub to link the image to the repository.
LABEL org.opencontainers.image.title="Kaladrius" \
      org.opencontainers.image.description="Open-source clinic management" \
      org.opencontainers.image.source="https://github.com/facchini-miguel/kaladrius" \
      org.opencontainers.image.documentation="https://kaladrius-docs.facchini.eti.br" \
      org.opencontainers.image.licenses="Apache-2.0"

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
# the whole site. No control socket (on by default since Gunicorn 25.1): nothing uses it, and
# it would be one more way to stop or reconfigure the server (decision 129).
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --threads 4 --no-control-socket"]
