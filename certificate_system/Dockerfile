# syntax=docker/dockerfile:1

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# System libs for Pillow/reportlab + psycopg2 runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        libpq5 \
        libjpeg62-turbo \
        zlib1g \
        libfreetype6 \
        liblcms2-2 \
        libwebp7 \
        libtiff6 \
        libopenjp2-7 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

# Create runtime directories
RUN mkdir -p /app/staticfiles /app/media /app/logs \
    && chmod -R 775 /app/staticfiles /app/media /app/logs

EXPOSE 8000

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
