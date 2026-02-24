# User Guide (Public Verification)

This guide is for **anyone verifying a certificate** (no login required).

## What you can do

- Verify a certificate by UUID.
- Verify by scanning a QR code printed on the certificate.
- Use the QR Tools page (if enabled) for camera scanning and helpful utilities.

## Verify a certificate

### Option A: Use the verification form

1. Open the public verification page: `/`
2. Paste the certificate UUID.
3. Submit.

You will be taken to the detail verification page:

- `/verify/<uuid>/`

### Option B: Use the QR code on the certificate

The QR code points to a public verification URL. Scanning it opens the same verification detail page:

- `/verify/<uuid>/`

## Understanding the result

A certificate is considered **verifiable** when:

- `status = VALID`
- `is_enabled = true`

If a certificate is revoked/disabled, it will be shown as **not valid for verification**.

## QR Tools (optional)

If the QR tools feature is enabled, you can open:

- `/qr-tools/`

This page is meant to help end users scan or work with QR codes.

## Privacy and logging

Verification attempts are logged for audit and troubleshooting, typically including:

- timestamp
- whether the certificate was valid
- requester IP
- user-agent

## Support / troubleshooting

If support asks for a **Request ID**, look for the `X-Request-ID` header value in your browser network tools (or ask the admin to locate it in logs).

If verification fails unexpectedly:

- Double-check the UUID is correct.
- Try opening the QR link directly.
- If it still fails, contact the issuing organization.
