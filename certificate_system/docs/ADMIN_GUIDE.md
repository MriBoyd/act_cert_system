# Admin Guide

This guide covers day-to-day administration: templates, generation, certificate management, and logs.

## Roles and access

The platform uses Django authentication and a custom `User` role.

### Required for admin pages

- `is_staff = true`
- Role is one of:
  - `SUPER_ADMIN`
  - `CERTIFICATE_ADMIN`

If the user is a Django `is_superuser`, they are treated as fully privileged.

### Clearing logs

Only **superusers** can clear log files from the Log Management UI.

## Login

- Admin login: `/login/`
- Admin dashboard: `/admin/dashboard/`

## Dashboard

The dashboard provides quick access to key admin functions.

## Template Management

- Templates list: `/admin/templates/`
- Create template: `/admin/templates/create/`

Templates define:

- background image
- dynamic field layout (JSON)
- active/inactive status

### Dynamic fields

Templates contain `dynamic_fields` JSON describing where text (and QR) should be drawn on the PDF.

Supported common fields:

- `recipient_name` / `name`
- `course_name` / `course`
- `issue_date` / `date`
- `serial_number`
- `certificate_id`
- `qr_code` (special)

For `qr_code`, you can specify:

- `x`, `y` (position)
- `size` (pixels)

If no `qr_code` field is included, a default QR placement is used.

## Generate a single certificate

- Page: `/admin/certificates/generate/`

You select a template and enter:

- recipient name / email
- course name
- issue date
- serial number

The system generates:

- a UUID certificate ID
- a QR code image pointing to the public verify URL
- a PDF certificate

Duplicate prevention:

- serial number is unique
- a content fingerprint is also unique

## Bulk generation (CSV)

- Page: `/admin/certificates/bulk/`

### Required CSV columns

- `recipient_name`
- `recipient_email`
- `course_name`
- `issue_date` (ISO format: `YYYY-MM-DD`)
- `serial_number`

Notes:

- Invalid rows are reported back (limited list in UI).
- Successful and failed counts are written to audit logs.

## Certificate Management

- List: `/admin/certificates/`
- Detail: `/admin/certificates/<uuid>/`
- Status/edit: `/admin/certificates/<uuid>/status/`

### Status and enable rules

A certificate cannot be enabled unless it is `VALID`.

### Downloads

If enabled by feature flags:

- PDF download: `/admin/certificates/<uuid>/download/pdf/`
- PNG download: `/admin/certificates/<uuid>/download/png/`
- JPG download: `/admin/certificates/<uuid>/download/jpg/`
- QR download: `/admin/certificates/<uuid>/download/qr/`

Download actions are audited.

The system generates and stores the downloadable artifacts on the certificate record (PDF, PNG, JPG, and QR). If a certificate is edited in a way that changes its printable fields, the artifacts are regenerated.

## Log Management

If enabled, admins can view logs in the UI:

- `/admin/logs/`

Available actions:

- view latest content with pagination
- search within the recent window
- download log files
- clear log files (**superuser only**)

Log types:

- Application: `app.log`
- Security: `security.log`
- Audit: `audit.log`

## Feature flags

Admin pages can be enabled/disabled using environment feature flags. If a feature is disabled, the route returns 404.

See the Config Reference for the full list.
