# Deployment Guide

This document describes a production-minded deployment approach, with a **Docker-first** path for sharing and deployment.

## Choose settings

Use the production settings module:

- `DJANGO_SETTINGS_MODULE=config.settings.production`

## Environment variables

Start from `.env.example` and set:

- `DJANGO_SECRET_KEY` (strong secret)
- `DJANGO_ALLOWED_HOSTS` (comma-separated)
- `SITE_BASE_URL` (public base URL)

Database (PostgreSQL):

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`

Logging:

- `LOG_DIR`
- `LOG_LEVEL`, `DJANGO_LOG_LEVEL`, `SECURITY_LOG_LEVEL`, `AUDIT_LOG_LEVEL`
- `LOG_JSON` (optional)

Feature flags:

- `FF_*` variables (see Config Reference)

Additional production variables:

- `DJANGO_SECURE_SSL_REDIRECT=true|false` (defaults to `true` in production settings; set `false` if you run plain HTTP)
- `DJANGO_CSRF_TRUSTED_ORIGINS=https://your-domain.example,https://www.your-domain.example` (comma-separated)

## Database

1. Provision PostgreSQL
2. Run migrations:

- `python manage.py migrate`

## Static and media

- Static files: run `python manage.py collectstatic` and serve from `STATIC_ROOT`.
- Media files: `MEDIA_ROOT` contains uploaded backgrounds and generated PDFs/QR images.

In production, you typically serve media via:

- Nginx/Apache mapping, or
- object storage (S3-compatible) using a Django storage backend.

## WSGI server

This project exposes a WSGI entrypoint:

- `config/wsgi.py`

A common setup is Gunicorn:

- `gunicorn config.wsgi:application`

Put Gunicorn behind a reverse proxy (Nginx) that terminates TLS.

## Docker (recommended for sharing/deployment)

This repo includes a production-oriented Docker setup:

- `Dockerfile` runs Gunicorn
- `docker-compose.yml` runs: Django (web) + Postgres (db) + Nginx (nginx)

Nginx serves:

- `/static/` from `STATIC_ROOT` (the `staticfiles` volume)
- `/media/` from `MEDIA_ROOT` (the `media` volume)

### Quick start

1. Create a `.env` (start from `.env.example`) and set at least:

- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `SITE_BASE_URL`
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`

2. Start containers:

- `docker compose up --build` (Docker Compose v2 plugin)
- or `docker-compose up --build` (legacy standalone binary)

3. Create a superuser:

- `docker compose exec web python manage.py createsuperuser`

On container start, the `web` service automatically runs:

- `python manage.py migrate --noinput`
- `python manage.py collectstatic --noinput`

The app will be available at:

- `http://localhost/` (Nginx)

### Persistent data and backups

The compose stack uses Docker volumes:

- `postgres_data`: PostgreSQL data
- `media`: uploaded backgrounds + generated files (PDF/QR/PNG/JPG)
- `staticfiles`: collected static assets
- `logs`: application logs

Back up at minimum:

- `postgres_data`
- `media`

### Updating the deployment

After pulling new code:

- `docker compose up --build -d`

Migrations run automatically on container start.

### HTTPS note

If you terminate TLS at a reverse proxy/load balancer, set:

- `DJANGO_SECURE_SSL_REDIRECT=true`
- `DJANGO_CSRF_TRUSTED_ORIGINS=https://your-domain.example`

Ensure your proxy sets `X-Forwarded-Proto=https` so Django can correctly detect HTTPS.

If you run plain HTTP (e.g. on a private network), keep `DJANGO_SECURE_SSL_REDIRECT=false`.

## Security settings

Production settings enable:

- secure cookies
- HSTS
- SSL redirect
- clickjacking protection

You must ensure TLS is correctly configured at the proxy.

## Operational notes

- Ensure the `LOG_DIR` is writable by the application user.
- Monitor `security.log` and `audit.log` for sensitive events.
- Back up the database and media storage.

## Troubleshooting

View logs:

- `docker compose logs -f web`
- `docker compose logs -f nginx`
- `docker compose logs -f db`

Common issues:

- 400 CSRF errors after enabling HTTPS: set `DJANGO_CSRF_TRUSTED_ORIGINS`.
- Redirect loops: ensure `X-Forwarded-Proto` is set by your proxy and matches the scheme.
- File uploads failing: check Nginx `client_max_body_size` in `docker/nginx/nginx.conf`.
