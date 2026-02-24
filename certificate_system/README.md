# Certificate Generation and Verification Platform (MVP)

Production-minded Django MVP for issuing, generating, and publicly verifying digital certificates with UUID-based security, QR verification, and PDF generation.

## Documentation

- User Guide: [docs/USER_GUIDE.md](docs/USER_GUIDE.md)
- Admin Guide: [docs/ADMIN_GUIDE.md](docs/ADMIN_GUIDE.md)
- Developer Guide: [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md)
- Deployment Guide: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
- Config Reference: [docs/CONFIG_REFERENCE.md](docs/CONFIG_REFERENCE.md)
- Troubleshooting: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- Integration API: [docs/API_INTEGRATION.md](docs/API_INTEGRATION.md)

### Build one PDF for all docs

- `python scripts/build_docs_pdf.py`

This writes: `docs/CertificatePlatform_Documentation.pdf`

## Tech Stack

- Backend: Django + Django REST Framework
- Frontend: Django Templates + Bootstrap 5
- Database: PostgreSQL
- Auth: Django auth + custom `User` roles + staff admin workflows
- Storage: Local `MEDIA_ROOT` with storage-abstraction-friendly file handling
- Document generation: ReportLab (PDF) + QRCode

## Why this project structure

```
certificate_system/
├── config/
│   ├── settings/           # Split settings for local/production safety
│   ├── urls.py             # Global URL routing
│   └── wsgi.py             # WSGI entrypoint
├── apps/
│   ├── certificates/       # Certificate domain: models, services, views, API
│   └── users/              # Custom user and role model
├── templates/              # UI templates (admin/public)
├── static/                 # Shared CSS/JS assets
├── media/                  # Generated files (PDFs, QR images, uploads)
└── manage.py
```

This structure keeps domain logic in `apps/certificates`, environment concerns in `config/settings`, and presentation in `templates/static`, which scales cleanly as API and UI grow.

## Core Features Implemented

- Custom user roles: `SUPER_ADMIN`, `CERTIFICATE_ADMIN`, `VIEWER`
- Certificate templates with dynamic field metadata
- Single certificate generation with duplicate prevention
- Bulk certificate generation from CSV upload
- Auto generation of:
  - UUID certificate ID
  - QR code pointing to public verification URL
  - PDF certificate file
- Public verification (no login):
  - by UUID entry
  - by QR URL endpoint
- Verification attempt logging with IP, user-agent, validity, timestamps
- Status controls: valid/revoked/disabled + enable/disable flags
- DRF endpoint for verification response

## Data Model Summary

- `users.User`: custom auth user with role and issuer flags
- `certificates.CertificateTemplate`: template background + field layout + status
- `certificates.Certificate`: UUID cert, serial, status, metadata, QR/PDF artifacts
- `certificates.VerificationLog`: immutable verification trail and request telemetry

## Setup

1. Create Python environment and install dependencies:
   - `python -m venv .venv`
   - `source .venv/bin/activate`
   - `pip install -r requirements.txt`
2. Configure environment:
   - `cp .env.example .env`
   - edit `.env` values
3. Create PostgreSQL database from `.env` values.
4. Run migrations:
   - `python manage.py makemigrations users certificates`
   - `python manage.py migrate`
5. Create admin user:
   - `python manage.py createsuperuser`
6. Run app:
   - `python manage.py runserver`

## Tests

Run the unittest suite:

- `python manage.py test`

`manage.py` automatically selects `config.settings.test` for the `test` command (SQLite in-memory + isolated media/log dirs) unless `DJANGO_SETTINGS_MODULE` is explicitly set.

## Main Routes

- Public verify form: `/`
- Verify by UUID: `/verify/<uuid>/`
- Verify API: `/api/verify/<uuid>/`
- Admin login: `/login/`
- Dashboard: `/admin/dashboard/`

## CSV Bulk Format

Required columns:

- `recipient_name`
- `recipient_email`
- `course_name`
- `issue_date` (ISO format `YYYY-MM-DD`)
- `serial_number`

## Security Notes

- UUID-based certificate IDs reduce enumeration risk
- CSRF middleware enabled by default
- Role-gated admin workflows with staff + role checks
- Input validation through Django forms and model constraints
- Verification actions are logged for auditing
- Production settings enable secure cookie and HSTS defaults

## Feature Flags

Feature flags are configured via environment variables and allow runtime control of modules without code changes.

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

Set values to `true` or `false` in `.env`.

## Logging

Logging is configured for security/audit/statistics use-cases and is designed to be production-manageable.

By default, logs go to:

- `logs/app.log`: general application + Django logs
- `logs/security.log`: security-relevant events (auth failures, access denials, Django security warnings)
- `logs/audit.log`: high-value business/audit events (template changes, downloads, verifications, etc.)

All files are rotated daily (midnight) with retention:

- `app.log`: 14 days
- `security.log` / `audit.log`: 30 days

Environment variables (add to `.env`):

- `LOG_DIR` (optional) — defaults to `<project>/logs`
- `LOG_LEVEL` — base level (`INFO`, `WARNING`, ...)
- `DJANGO_LOG_LEVEL` — Django framework log level
- `SECURITY_LOG_LEVEL` — security logger level
- `AUDIT_LOG_LEVEL` — audit logger level
- `LOG_JSON` — set `true` to output JSON logs (requires `python-json-logger`)

Every log line includes request context when available: request id (`X-Request-ID`), user id, IP, method, and path.

## Future Enhancements (S3-ready path)

- Replace default file storage with S3 backend (no model changes required)
- Add asynchronous generation queue for large bulk imports
- Add signed verification links and rate-limiting middleware
