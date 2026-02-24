import io
import uuid

import qrcode
from django.core.files.base import ContentFile


def generate_qr_image(verification_url: str, cert_uuid: uuid.UUID) -> ContentFile:
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(verification_url)
    qr.make(fit=True)

    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    buffer.seek(0)

    return ContentFile(buffer.read(), name=f"{cert_uuid}.png")
