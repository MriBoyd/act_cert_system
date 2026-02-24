# Integration API (for external platforms)

This project includes an Integration API designed for other systems to:

- list templates
- create certificates
- read certificate details
- update certificate status
- download certificate files (PDF + PNG + JPG + QR)

The API uses **scoped API keys**.

## Enable/disable

- Feature flag: `FF_INTEGRATION_API=true|false`

If disabled, endpoints return `404`.

## Authentication

Send the API key in either header:

- `Authorization: Api-Key <YOUR_KEY>`
- `X-API-Key: <YOUR_KEY>`

The key is never stored in plaintext in the database.

## Scopes

Scopes are strings stored on the API key record.

Current scopes:

- `templates:read`
- `templates:write`
- `certificates:read`
- `certificates:write`
- `certificates:delete`
- `files:read`

## Create an API key

Create a user first (recommended: a dedicated service user), then run:

- `python manage.py create_api_key --username <user> --name "Partner A" --scopes templates:read,certificates:read,certificates:write,files:read`

Optional expiry:

- `python manage.py create_api_key --username <user> --name "Partner A" --expires-days 90`

The command prints the raw key once. Store it securely.

## Endpoints

### List templates

- `GET /api/integration/templates/`
- Scope: `templates:read`

Example:

- `curl -H "Authorization: Api-Key $API_KEY" http://localhost:8000/api/integration/templates/`

### Create certificate

- `POST /api/integration/certificates/`
- Scope: `certificates:write`

Request JSON:

- `template_id` (UUID)
- `recipient_name`
- `recipient_email` (optional)
- `course_name`
- `issue_date` (`YYYY-MM-DD`)
- `serial_number`

Example:

```bash
curl -X POST \
  -H "Authorization: Api-Key $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "<uuid>",
    "recipient_name": "John Doe",
    "recipient_email": "john@example.com",
    "course_name": "Django 101",
    "issue_date": "2025-01-01",
    "serial_number": "SER-1001"
  }' \
  http://localhost:8000/api/integration/certificates/
```

Response includes:

- `certificate_id`
- `verification_url`
- `pdf_download_url`
- `qr_download_url`

Duplicate behavior:

- If serial/fingerprint already exists, returns `409`.

### Bulk create certificates (JSON)

- `POST /api/integration/certificates/bulk/`
- Scope: `certificates:write`

You can provide a shared `template_id` once, plus a `certificates` array.

Limits:

- Max 500 certificates per request.

If you do not provide a top-level `template_id`, each item in `certificates` must include its own `template_id`.

Example:

```bash
curl -X POST \
  -H "Authorization: Api-Key $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "<uuid>",
    "certificates": [
      {
        "recipient_name": "John Doe",
        "recipient_email": "john@example.com",
        "course_name": "Django 101",
        "issue_date": "2025-01-01",
        "serial_number": "SER-2001"
      },
      {
        "recipient_name": "Jane Doe",
        "recipient_email": "jane@example.com",
        "course_name": "Django 101",
        "issue_date": "2025-01-01",
        "serial_number": "SER-2002"
      }
    ]
  }' \
  http://localhost:8000/api/integration/certificates/bulk/
```

The response contains `created`, `failed`, and a `results` array aligned to the input order, with per-item errors (including duplicates).

### Get certificate details

- `GET /api/integration/certificates/<uuid>/`
- Scope: `certificates:read`

### Update certificate status

- `PATCH /api/integration/certificates/<uuid>/status/`
- Scope: `certificates:write`

Body example:

- `{ "status": "REVOKED", "is_enabled": false }`

Validation:

- A certificate cannot be enabled unless its status is `VALID`.

### Download PDF

- `GET /api/integration/certificates/<uuid>/download/pdf/`
- Scope: `files:read`

### Download PNG

- `GET /api/integration/certificates/<uuid>/download/png/`
- Scope: `files:read`

### Download JPG

- `GET /api/integration/certificates/<uuid>/download/jpg/`
- Scope: `files:read`

### Download QR

- `GET /api/integration/certificates/<uuid>/download/qr/`
- Scope: `files:read`

## Notes

- The public verification endpoint remains separate: `GET /api/verify/<uuid>/`.
- For production, set `SITE_BASE_URL` so QR codes point to the correct public domain.

## Template CRUD

### Create template

- `POST /api/integration/templates/`
- Scope: `templates:write`
- Content-Type: `multipart/form-data`

Fields:

- `name`
- `issuer_name`
- `background_image` (file)
- `dynamic_fields` (JSON)
- `is_active` (optional)

### Get template

- `GET /api/integration/templates/<uuid>/`
- Scope: `templates:read`

### Update template

- `PATCH /api/integration/templates/<uuid>/`
- Scope: `templates:write`

### Delete template

- `DELETE /api/integration/templates/<uuid>/`
- Scope: `templates:write`

If the template is referenced by certificates, deletion returns `409`.

## Certificate CRUD

### List certificates

- `GET /api/integration/certificates/`
- Scope: `certificates:read`

Optional query params:

- `status`
- `template_id`
- `serial_number`
- `search`
- `limit` (1-500, default 100)

### Update certificate

- `PATCH /api/integration/certificates/<uuid>/`
- Scope: `certificates:write`

If core printable fields change, the system regenerates the PDF/QR.

### Delete certificate

- `DELETE /api/integration/certificates/<uuid>/`
- Scope: `certificates:delete`
