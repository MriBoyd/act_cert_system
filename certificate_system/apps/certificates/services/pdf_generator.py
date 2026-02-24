import io
from pathlib import Path

from django.core.files.base import ContentFile
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfgen import canvas


FIELD_MAP = {
    "name": "recipient_name",
    "recipient_name": "recipient_name",
    "course": "course_name",
    "course_name": "course_name",
    "date": "issue_date",
    "issue_date": "issue_date",
    "serial_number": "serial_number",
    "certificate_id": "id",
}


def _field_value(certificate, field_name: str):
    model_field = FIELD_MAP.get(field_name, field_name)
    value = getattr(certificate, model_field, None)
    if value is None:
        value = certificate.metadata.get(field_name, "")
    return str(value)


def generate_certificate_pdf(certificate) -> ContentFile:
    """Generate PDF content based on template background and dynamic fields."""
    buffer = io.BytesIO()
    page_width, page_height = landscape(A4)
    pdf = canvas.Canvas(buffer, pagesize=(page_width, page_height))

    background_path = Path(certificate.template.background_image.path)
    if background_path.exists():
        pdf.drawImage(str(background_path), 0, 0, width=page_width, height=page_height)

    qr_drawn = False
    overlay_drawn = {"logo_image": False, "signature_image": False}
    for field in certificate.template.dynamic_fields:
        field_name = field.get("name")
        if field_name == "qr_code":
            qr_size = float(field.get("size", 110))
            qr_x = float(field.get("x", page_width - qr_size - 36))
            qr_y = float(field.get("y", 36))
            if certificate.qr_code_image and getattr(certificate.qr_code_image, "path", None):
                qr_path = Path(certificate.qr_code_image.path)
                if qr_path.exists():
                    pdf.drawImage(str(qr_path), qr_x, qr_y, width=qr_size, height=qr_size, mask="auto")
                    qr_drawn = True
            continue

        if field_name in {"logo", "logo_image", "signature", "signature_image"} or field.get("type") == "image":
            # Resolve which certificate field to use.
            if field_name in {"logo", "logo_image"}:
                image_field = getattr(certificate, "logo_image", None)
                overlay_key = "logo_image"
                default_w = 120
                default_h = 120
                default_x = 36
                default_y = page_height - default_h - 36
            elif field_name in {"signature", "signature_image"}:
                image_field = getattr(certificate, "signature_image", None)
                overlay_key = "signature_image"
                default_w = 160
                default_h = 60
                default_x = 36
                default_y = 36
            else:
                # Unknown image slot
                image_field = None
                overlay_key = None
                default_w = 120
                default_h = 120
                default_x = 36
                default_y = page_height - default_h - 36

            if image_field and getattr(image_field, "name", ""):
                try:
                    img_path = Path(image_field.path)
                except ValueError:
                    img_path = None

                if img_path and img_path.exists():
                    w = float(field.get("width", field.get("w", default_w)))
                    h = float(field.get("height", field.get("h", default_h)))
                    x = float(field.get("x", default_x))
                    y = float(field.get("y", default_y))
                    pdf.drawImage(str(img_path), x, y, width=w, height=h, mask="auto")
                    if overlay_key:
                        overlay_drawn[overlay_key] = True
            continue

        x = float(field.get("x", 100))
        y = float(field.get("y", 100))
        font_size = int(field.get("font_size", 18))

        pdf.setFont("Helvetica", font_size)
        pdf.drawString(x, y, _field_value(certificate, field_name))

    if not qr_drawn and certificate.qr_code_image and getattr(certificate.qr_code_image, "path", None):
        qr_path = Path(certificate.qr_code_image.path)
        if qr_path.exists():
            qr_size = 110
            pdf.drawImage(
                str(qr_path),
                page_width - qr_size - 36,
                36,
                width=qr_size,
                height=qr_size,
                mask="auto",
            )

    # Default placement for overlays if not explicitly drawn via dynamic_fields
    if not overlay_drawn["logo_image"] and getattr(certificate, "logo_image", None) and getattr(certificate.logo_image, "name", ""):
        try:
            logo_path = Path(certificate.logo_image.path)
        except ValueError:
            logo_path = None
        if logo_path and logo_path.exists():
            w = 120
            h = 120
            pdf.drawImage(str(logo_path), 36, page_height - h - 36, width=w, height=h, mask="auto")

    if (
        not overlay_drawn["signature_image"]
        and getattr(certificate, "signature_image", None)
        and getattr(certificate.signature_image, "name", "")
    ):
        try:
            sig_path = Path(certificate.signature_image.path)
        except ValueError:
            sig_path = None
        if sig_path and sig_path.exists():
            w = 160
            h = 60
            pdf.drawImage(str(sig_path), 36, 36, width=w, height=h, mask="auto")

    # Dynamic extra overlays (default placement: stacked at top-right)
    try:
        extra_overlays = list(getattr(certificate, "overlay_images", []).all())
    except Exception:  # noqa: BLE001
        extra_overlays = []

    if extra_overlays:
        margin = 36
        w = 80
        h = 80
        gap = 10
        x = page_width - margin - w
        y = page_height - margin - h
        for overlay in extra_overlays:
            image_field = getattr(overlay, "image", None)
            if not image_field or not getattr(image_field, "name", ""):
                continue
            try:
                img_path = Path(image_field.path)
            except ValueError:
                continue
            if not img_path.exists():
                continue
            pdf.drawImage(str(img_path), x, y, width=w, height=h, mask="auto")
            y -= (h + gap)
            if y < margin:
                break

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    return ContentFile(buffer.read(), name=f"{certificate.id}.pdf")
