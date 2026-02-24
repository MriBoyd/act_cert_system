# Troubleshooting

## Tests try to use Postgres

By default, `manage.py` auto-selects the test settings for the `test` command.

If you override `DJANGO_SETTINGS_MODULE`, ensure it is:

- `config.settings.test`

## Postgres connection errors in local dev

Check values in `.env`:

- `POSTGRES_HOST`, `POSTGRES_PORT`
- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`

Then ensure PostgreSQL is running and reachable.

## Verification URL in QR is wrong

The QR verification URL is built from:

- `SITE_BASE_URL`

Update it to the correct public domain.

## PDF generation issues

Common causes:

- template background image missing
- media directory not writable
- ReportLab font/image support issues

Verify:

- `MEDIA_ROOT` exists and is writable
- the template background image file exists in storage

## Log management page is missing

Check feature flag:

- `FF_LOG_MANAGEMENT=true`

Also ensure the logged-in user is staff and has the right role.

## Logs not being written

Check:

- `LOG_DIR` exists and is writable
- log levels are not set too high

Files expected:

- `app.log`
- `security.log`
- `audit.log`

## Admin pages return 404

Many admin routes are guarded by feature flags. If disabled, they intentionally return 404.

Check the relevant `FF_*` variable.
