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

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    return ContentFile(buffer.read(), name=f"{certificate.id}.pdf")
