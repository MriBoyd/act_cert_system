# Developer Guide

This guide is for developers working on the Django codebase.

## Tech stack

- Django + Django REST Framework
- Templates: Django Templates + Bootstrap 5
- PDF generation: ReportLab
- QR generation: `qrcode`

## Project layout

- `apps/`
  - `apps/certificates/`: domain models, services, admin/public views, DRF verify API
  - `apps/users/`: custom user model and auth-related signals
- `config/`
  - `config/settings/`: `base.py`, `local.py`, `production.py`, `test.py`
  - logging helpers and request context middleware

## Local development

1. Create a virtual environment

   - `python -m venv .venv`
   - `source .venv/bin/activate`

2. Install dependencies

   - `pip install -r requirements.txt`

3. Configure environment

   - `cp .env.example .env`
   - edit `.env`

4. Database + migrations (PostgreSQL for local)

   - `python manage.py migrate`
   - `python manage.py createsuperuser`

5. Run server

   - `python manage.py runserver`

## Settings selection

- Default dev run uses: `config.settings.local`
- Production should use: `config.settings.production`
- Tests use: `config.settings.test`

Note: `manage.py` automatically selects `config.settings.test` for the `test` command unless you explicitly set `DJANGO_SETTINGS_MODULE`.

## Logging architecture

Logging is split for operational clarity:

- `app` logger: general application information
- `security` logger: authentication and access-related events
- `audit` logger: high-value business events (downloads, status changes, template edits, verifications)

Request context is injected via middleware so logs can include:

- request id (`X-Request-ID`)
- user id
- ip
- method + path

Log config is built by `config/logging_config.py` and activated in settings.

## Feature flags

Feature flags are read from settings (`FEATURE_FLAGS`) and are enforced in views via the `require_feature()` decorator.

## Key services

- Certificate creation:
  - `apps/certificates/services/certificate_service.py`
- PDF generation:
  - `apps/certificates/services/pdf_generator.py`
- QR generation:
  - `apps/certificates/services/qr_service.py`

## Testing

Run tests:

- `python manage.py test`

The test settings use SQLite in-memory and isolate media/log directories.

### Writing tests

- Prefer Django `TestCase`.
- Use test factories in `apps/certificates/tests/utils.py`.
- Use `override_settings()` when testing logging directories or feature flags.

## Code style

- Keep changes minimal and consistent with existing patterns.
- Use services for pure business logic.
- Avoid writing to disk outside Django storage / `MEDIA_ROOT`.
