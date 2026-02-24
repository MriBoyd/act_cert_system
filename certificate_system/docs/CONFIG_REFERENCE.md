# Configuration Reference

This project is configured primarily via environment variables.

## Core Django

- `DJANGO_ENV`: `local` or `production` (used by `config/settings/__init__.py`)
- `DJANGO_SECRET_KEY`: Django secret key
- `DJANGO_ALLOWED_HOSTS`: comma-separated list (e.g. `example.com,www.example.com`)
- `SITE_BASE_URL`: base URL used to generate verification URLs in QR codes

## Database (PostgreSQL)

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`

## Logging

- `LOG_DIR`: directory path for log files
- `LOG_LEVEL`: base log level
- `DJANGO_LOG_LEVEL`: Django log level
- `SECURITY_LOG_LEVEL`: security logger level
- `AUDIT_LOG_LEVEL`: audit logger level
- `LOG_JSON`: `true/false` to output JSON logs

## Feature flags

Feature flags are boolean (`true/false`) and control modules at runtime.

- `FF_ADMIN_DASHBOARD`
- `FF_TEMPLATE_MANAGEMENT`
- `FF_CERTIFICATE_GENERATION`
- `FF_BULK_GENERATION`
- `FF_CERTIFICATE_MANAGEMENT`
- `FF_CERTIFICATE_DETAIL`
- `FF_CERTIFICATE_DOWNLOAD`
- `FF_PUBLIC_VERIFICATION`
- `FF_QR_SCANNER`
- `FF_VERIFICATION_API`
- `FF_VERIFICATION_ANIMATION`
- `FF_LOG_MANAGEMENT`
- `FF_INTEGRATION_API`
