# act_cert_system

A production-minded Django certificate generation and verification platform for issuing digital certificates, generating PDFs and QR codes, and enabling public certificate verification without login.

## Overview

`act_cert_system` is a Django-based certificate platform designed for organizations that need to:

- create certificate templates
- issue individual or bulk certificates
- generate PDF certificates with QR codes
- verify certificates publicly by UUID or QR link
- track verification attempts for audit and troubleshooting
- optionally integrate with external systems through a scoped API

The application uses a role-based admin workflow, Django REST Framework for API endpoints, and feature flags to enable or hide modules at runtime.

## Key Features

- Custom user roles:
  - `SUPER_ADMIN`
  - `CERTIFICATE_ADMIN`
  - `VIEWER`
- Certificate templates with configurable dynamic fields
- Single certificate generation
- Bulk certificate generation from CSV
- UUID-based certificate IDs
- QR code generation linked to public verification URLs
- PDF certificate generation
- Public certificate verification without login
- Verification logging with:
  - timestamp
  - IP address
  - user-agent
  - validity result
  - verification source
- Status management:
  - valid
  - revoked
  - disabled
- Downloadable certificate artifacts:
  - PDF
  - PNG
  - JPG
  - QR image
- Integration API with scoped API keys
- Docker-first deployment support

## Tech Stack

- Backend: Django
- API: Django REST Framework
- Frontend: Django Templates + Bootstrap 5
- Database: PostgreSQL
- PDF generation: ReportLab
- QR generation: `qrcode`
- Deployment: Docker, Gunicorn, Nginx

## Project Structure

```text
certificate_system/
├── config/
│   ├── settings/           # local, production, test settings
│   ├── urls.py             # global URL routing
│   └── wsgi.py             # WSGI entrypoint
├── apps/
│   ├── certificates/       # certificate models, services, views, API
│   └── users/              # custom user model and auth logic
├── templates/              # public and admin UI templates
├── static/                 # CSS/JS assets
├── media/                  # uploaded backgrounds and generated files
└── manage.py
```

This structure keeps domain logic in `apps/certificates`, environment configuration in `config/settings`, and UI assets in `templates` and `static`.

## Main Capabilities

### Certificate Management
- Create certificate templates
- Define dynamic certificate field layouts
- Generate a single certificate
- Generate certificates in bulk from CSV
- Prevent duplicates using serial number and fingerprint checks
- Store generated artifacts on the certificate record

### Public Verification
- Verify certificates by UUID
- Verify by scanning the QR code on the certificate
- View results on a public verification page
- Access a verification API endpoint for integrations

### Administration
- Manage templates
- Generate certificates
- View certificate records
- Update certificate status
- Download certificate files
- View verification logs
- Manage application logs

### Integrations
- List certificate templates
- Create certificates through API requests
- Bulk-create certificates through API
- Retrieve certificate details
- Update certificate status
- Download generated files
- Use scoped API keys for access control

## Roles and Access

The project uses Django authentication plus a custom role field.

### Roles
- `SUPER_ADMIN`: full platform access
- `CERTIFICATE_ADMIN`: can manage certificates and templates
- `VIEWER`: read-only or limited access depending on feature flags and page restrictions

### Admin Access
Most administrative pages require:
- `is_staff = true`
- a permitted role
- or `is_superuser = true` for full access

## Core Data Models

### `users.User`
Custom Django user model with:
- username
- email
- role
- issuer flags
- public UUID identifier

### `certificates.CertificateTemplate`
Represents a reusable certificate template with:
- template name
- issuer name
- background image
- dynamic field layout
- active/inactive status

### `certificates.Certificate`
Represents an issued certificate with:
- certificate UUID
- serial number
- recipient details
- course details
- issue date
- status
- enable/disable state
- PDF/PNG/JPG/QR artifacts
- issuing user

### `certificates.VerificationLog`
Stores certificate verification attempts with:
- certificate UUID
- linked certificate if available
- IP address
- user-agent
- source of verification
- result
- timestamp

## Main Routes

### Public
- `/` — public verification form
- `/verify/<uuid>/` — public verification result page
- `/api/verify/<uuid>/` — verification API endpoint
- `/qr-tools/` — QR tools page, if enabled

### Admin
- `/login/` — admin login
- `/admin/dashboard/` — admin dashboard
- `/admin/templates/` — template list
- `/admin/templates/create/` — create template
- `/admin/certificates/generate/` — generate a certificate
- `/admin/certificates/bulk/` — bulk generation
- `/admin/certificates/` — certificate list
- `/admin/certificates/<uuid>/` — certificate detail
- `/admin/certificates/<uuid>/status/` — update certificate status
- `/admin/logs/` — log management, if enabled

### API
- `/api/integration/templates/`
- `/api/integration/certificates/`
- `/api/integration/certificates/bulk/`
- additional certificate detail, status, and file endpoints under the integration API namespace

## Public Verification Flow

A certificate can be verified in two ways:

1. **Manual UUID lookup**
   - the user enters the certificate UUID into the public verification form
2. **QR code scan**
   - the QR code on the certificate points to the public verification URL

A certificate is considered verifiable when:

- `status == VALID`
- `is_enabled == true`

If a certificate is revoked or disabled, the system shows it as invalid for verification.

## Certificate Generation Flow

When an admin generates a certificate, the system:

1. loads the selected template
2. validates recipient and course data
3. assigns a UUID certificate ID
4. generates a QR code pointing to the public verification URL
5. renders a PDF certificate
6. stores generated artifacts on the certificate record
7. writes audit entries where applicable

## Bulk Generation

The bulk CSV workflow supports issuing many certificates at once.

### Required CSV Columns
- `recipient_name`
- `recipient_email`
- `course_name`
- `issue_date` in `YYYY-MM-DD` format
- `serial_number`

Invalid rows are reported back in the admin UI, while successful and failed records are logged.

## Integration API

The platform includes a scoped API for external systems.

### Authentication
Send the API key in one of these headers:

- `Authorization: Api-Key <YOUR_KEY>`
- `X-API-Key: <YOUR_KEY>`

### Common Scopes
- `templates:read`
- `templates:write`
- `certificates:read`
- `certificates:write`
- `certificates:delete`
- `files:read`

### Example Use Cases
- partner platforms issuing certificates
- HR or training systems synchronizing certification data
- external dashboards reading verification status
- automatic file retrieval for downstream systems

## Configuration

The application is configured primarily through environment variables.

### Core
- `DJANGO_ENV`
- `DJANGO_SECRET_KEY`
- `DJANGO_ALLOWED_HOSTS`
- `SITE_BASE_URL`

### Database
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`

### Logging
- `LOG_DIR`
- `LOG_LEVEL`
- `DJANGO_LOG_LEVEL`
- `SECURITY_LOG_LEVEL`
- `AUDIT_LOG_LEVEL`
- `LOG_JSON`

### Feature Flags
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

## Documentation

Additional documentation is available inside the repo:

- [User Guide](certificate_system/docs/USER_GUIDE.md)
- [Admin Guide](certificate_system/docs/ADMIN_GUIDE.md)
- [Developer Guide](certificate_system/docs/DEVELOPER_GUIDE.md)
- [Deployment Guide](certificate_system/docs/DEPLOYMENT.md)
- [Config Reference](certificate_system/docs/CONFIG_REFERENCE.md)
- [Troubleshooting](certificate_system/docs/TROUBLESHOOTING.md)
- [Integration API](certificate_system/docs/API_INTEGRATION.md)

## Local Development

### 1. Create a virtual environment
```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env
```

Edit `.env` with your local settings.

### 4. Set up the database
Create and configure a PostgreSQL database that matches your `.env` values.

### 5. Run migrations
```bash
python manage.py makemigrations users certificates
python manage.py migrate
```

### 6. Create an admin user
```bash
python manage.py createsuperuser
```

### 7. Run the development server
```bash
python manage.py runserver
```

## Testing

Run the test suite with:

```bash
python manage.py test
```

The test settings use SQLite in memory and isolated media/log directories unless `DJANGO_SETTINGS_MODULE` is explicitly set.

## Deployment

This project is designed for Docker-based deployment.

### Recommended production setup
- Django running via Gunicorn
- Nginx as reverse proxy
- PostgreSQL for the database
- persistent volumes for:
  - media files
  - static files
  - logs

### Typical production steps
1. Set `DJANGO_SETTINGS_MODULE=config.settings.production`
2. Set required environment variables
3. Run migrations
4. Collect static files
5. Start Gunicorn behind Nginx

## Security Notes

- Certificate verification is public, but issuing is restricted
- API keys should be stored securely and never committed
- QR codes point to public verification URLs built from `SITE_BASE_URL`
- Verification events are logged for auditability
- Sensitive admin routes may be hidden behind feature flags

## Troubleshooting

Common issues:
- wrong QR verification URL
- missing or unwritable media directory
- PostgreSQL connection problems
- disabled feature flags causing 404s
- PDF generation issues due to missing assets

See the troubleshooting guide for more detail.

## License

No license file was detected in the repository. Add one if you intend to distribute or open-source the project.

## Acknowledgements

Built with Django, Django REST Framework, ReportLab, and qrcode.
