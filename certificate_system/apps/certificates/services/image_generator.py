from __future__ import annotations

import io
from pathlib import Path

from django.core.files.base import ContentFile
from reportlab.lib.pagesizes import A4, landscape


def _load_font(size_px: int):
    from PIL import ImageFont  # pillow

    # Common Linux font path; fallback to default bitmap font.
    for candidate in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]:
        try:
            if Path(candidate).exists():
                return ImageFont.truetype(candidate, size_px)
        except Exception:  # noqa: BLE001
            continue

    try:
        return ImageFont.load_default()
    except Exception:  # noqa: BLE001
        return None


def _pdf_points_to_pixels(*, x_pt: float, y_pt: float, page_w_pt: float, page_h_pt: float, img_w_px: int, img_h_px: int):
    sx = img_w_px / page_w_pt
    sy = img_h_px / page_h_pt
    x_px = int(round(x_pt * sx))
    y_px_from_bottom = y_pt * sy
    return x_px, y_px_from_bottom, sx, sy


def generate_certificate_image(certificate, *, fmt: str = "PNG", dpi: int = 300) -> ContentFile:
    """Render a certificate as an image (PNG/JPG) using the template background.

    Coordinates in template dynamic_fields are assumed to be in PDF points for A4 landscape
    (same coordinate system as pdf_generator), and will be scaled to the output image.

    Returns a ContentFile with the binary image data.
    """

    from PIL import Image, ImageDraw  # pillow

    page_w_pt, page_h_pt = landscape(A4)

    # Target size in pixels. 300 DPI A4 landscape ~= 3508x2480
    img_w_px = int(round((page_w_pt / 72.0) * dpi))
    img_h_px = int(round((page_h_pt / 72.0) * dpi))

    background = None
    bg_path = getattr(getattr(certificate.template, "background_image", None), "path", None)
    if bg_path:
        p = Path(bg_path)
        if p.exists():
            background = Image.open(p).convert("RGB")

    if background is None:
        background = Image.new("RGB", (img_w_px, img_h_px), (255, 255, 255))

    background = background.resize((img_w_px, img_h_px))
    draw = ImageDraw.Draw(background)

    # QR image (prefer stored, else skip)
    qr_image = None
    qr_path = getattr(getattr(certificate, "qr_code_image", None), "path", None)
    if qr_path:
        p = Path(qr_path)
        if p.exists():
            qr_image = Image.open(p).convert("RGBA")

    def field_value(field_name: str) -> str:
        from apps.certificates.services.pdf_generator import _field_value

        return _field_value(certificate, field_name)

    qr_drawn = False
    overlays_drawn = {"logo_image": False, "signature_image": False}
    for field in certificate.template.dynamic_fields:
        name = field.get("name")
        if not name:
            continue

        if name == "qr_code":
            if qr_image is None:
                continue

            size_pt = float(field.get("size", 110))
            x_pt = float(field.get("x", page_w_pt - size_pt - 36))
            y_pt = float(field.get("y", 36))

            x_px, y_px_from_bottom, sx, sy = _pdf_points_to_pixels(
                x_pt=x_pt,
                y_pt=y_pt,
                page_w_pt=page_w_pt,
                page_h_pt=page_h_pt,
                img_w_px=img_w_px,
                img_h_px=img_h_px,
            )
            size_px = int(round(size_pt * min(sx, sy)))
            y_px = int(round(img_h_px - y_px_from_bottom - size_px))

            qr_resized = qr_image.resize((size_px, size_px))
            background.paste(qr_resized, (x_px, y_px), qr_resized)
            qr_drawn = True
            continue

        if name in {"logo", "logo_image", "signature", "signature_image"} or field.get("type") == "image":
            if name in {"logo", "logo_image"}:
                overlay_field = getattr(certificate, "logo_image", None)
                overlay_key = "logo_image"
                default_w_pt = 120
                default_h_pt = 120
                default_x_pt = 36
                default_y_pt = page_h_pt - default_h_pt - 36
            elif name in {"signature", "signature_image"}:
                overlay_field = getattr(certificate, "signature_image", None)
                overlay_key = "signature_image"
                default_w_pt = 160
                default_h_pt = 60
                default_x_pt = 36
                default_y_pt = 36
            else:
                overlay_field = None
                overlay_key = None
                default_w_pt = 120
                default_h_pt = 120
                default_x_pt = 36
                default_y_pt = page_h_pt - default_h_pt - 36

            overlay_img = None
            overlay_path = None
            if overlay_field and getattr(overlay_field, "name", ""):
                try:
                    overlay_path = overlay_field.path
                except ValueError:
                    overlay_path = None

            if overlay_path:
                p = Path(overlay_path)
                if p.exists():
                    try:
                        overlay_img = Image.open(p).convert("RGBA")
                    except Exception:  # noqa: BLE001
                        overlay_img = None

            if overlay_img is None:
                continue

            w_pt = float(field.get("width", field.get("w", default_w_pt)))
            h_pt = float(field.get("height", field.get("h", default_h_pt)))
            x_pt = float(field.get("x", default_x_pt))
            y_pt = float(field.get("y", default_y_pt))

            x_px, y_px_from_bottom, sx, sy = _pdf_points_to_pixels(
                x_pt=x_pt,
                y_pt=y_pt,
                page_w_pt=page_w_pt,
                page_h_pt=page_h_pt,
                img_w_px=img_w_px,
                img_h_px=img_h_px,
            )
            w_px = max(1, int(round(w_pt * sx)))
            h_px = max(1, int(round(h_pt * sy)))
            y_px = int(round(img_h_px - y_px_from_bottom - h_px))

            overlay_resized = overlay_img.resize((w_px, h_px))
            background.paste(overlay_resized, (x_px, y_px), overlay_resized)
            if overlay_key:
                overlays_drawn[overlay_key] = True
            continue

        x_pt = float(field.get("x", 100))
        y_pt = float(field.get("y", 100))
        font_size_pt = int(field.get("font_size", 18))

        x_px, y_px_from_bottom, _sx, sy = _pdf_points_to_pixels(
            x_pt=x_pt,
            y_pt=y_pt,
            page_w_pt=page_w_pt,
            page_h_pt=page_h_pt,
            img_w_px=img_w_px,
            img_h_px=img_h_px,
        )

        font_size_px = max(8, int(round(font_size_pt * sy)))
        font = _load_font(font_size_px)

        # Convert PDF bottom-origin y to image top-origin y.
        # We approximate baseline by shifting up by font size.
        y_px = int(round(img_h_px - y_px_from_bottom - font_size_px))

        value = field_value(name)
        if font is not None:
            draw.text((x_px, y_px), value, fill=(0, 0, 0), font=font)
        else:
            draw.text((x_px, y_px), value, fill=(0, 0, 0))

    if not qr_drawn and qr_image is not None:
        # Default placement similar to PDF generator
        size_pt = 110
        x_pt = page_w_pt - size_pt - 36
        y_pt = 36
        x_px, y_px_from_bottom, sx, sy = _pdf_points_to_pixels(
            x_pt=x_pt,
            y_pt=y_pt,
            page_w_pt=page_w_pt,
            page_h_pt=page_h_pt,
            img_w_px=img_w_px,
            img_h_px=img_h_px,
        )
        size_px = int(round(size_pt * min(sx, sy)))
        y_px = int(round(img_h_px - y_px_from_bottom - size_px))
        qr_resized = qr_image.resize((size_px, size_px))
        background.paste(qr_resized, (x_px, y_px), qr_resized)

    # Default overlays if not drawn via dynamic_fields
    def _try_default_overlay(field_name: str, *, x_pt: float, y_pt: float, w_pt: float, h_pt: float):
        overlay_field = getattr(certificate, field_name, None)
        if not overlay_field or not getattr(overlay_field, "name", ""):
            return
        try:
            overlay_path = overlay_field.path
        except ValueError:
            return

        p = Path(overlay_path)
        if not p.exists():
            return
        try:
            overlay_img = Image.open(p).convert("RGBA")
        except Exception:  # noqa: BLE001
            return

        x_px, y_px_from_bottom, sx, sy = _pdf_points_to_pixels(
            x_pt=x_pt,
            y_pt=y_pt,
            page_w_pt=page_w_pt,
            page_h_pt=page_h_pt,
            img_w_px=img_w_px,
            img_h_px=img_h_px,
        )
        w_px = max(1, int(round(w_pt * sx)))
        h_px = max(1, int(round(h_pt * sy)))
        y_px = int(round(img_h_px - y_px_from_bottom - h_px))
        overlay_resized = overlay_img.resize((w_px, h_px))
        background.paste(overlay_resized, (x_px, y_px), overlay_resized)

    if not overlays_drawn["logo_image"]:
        _try_default_overlay(
            "logo_image",
            x_pt=36,
            y_pt=page_h_pt - 120 - 36,
            w_pt=120,
            h_pt=120,
        )

    if not overlays_drawn["signature_image"]:
        _try_default_overlay(
            "signature_image",
            x_pt=36,
            y_pt=36,
            w_pt=160,
            h_pt=60,
        )

    # Dynamic extra overlays (default placement: stacked at top-right)
    try:
        extra_overlays = list(getattr(certificate, "overlay_images", []).all())
    except Exception:  # noqa: BLE001
        extra_overlays = []

    if extra_overlays:
        # Default sizes in PDF points
        w_pt = 80
        h_pt = 80
        gap_pt = 10
        margin_pt = 36

        x_pt = page_w_pt - margin_pt - w_pt
        y_pt = page_h_pt - margin_pt - h_pt

        for overlay in extra_overlays:
            image_field = getattr(overlay, "image", None)
            if not image_field or not getattr(image_field, "name", ""):
                continue
            try:
                overlay_path = image_field.path
            except ValueError:
                continue
            p = Path(overlay_path)
            if not p.exists():
                continue
            try:
                overlay_img = Image.open(p).convert("RGBA")
            except Exception:  # noqa: BLE001
                continue

            x_px, y_px_from_bottom, sx, sy = _pdf_points_to_pixels(
                x_pt=x_pt,
                y_pt=y_pt,
                page_w_pt=page_w_pt,
                page_h_pt=page_h_pt,
                img_w_px=img_w_px,
                img_h_px=img_h_px,
            )
            w_px = max(1, int(round(w_pt * sx)))
            h_px = max(1, int(round(h_pt * sy)))
            y_px = int(round(img_h_px - y_px_from_bottom - h_px))

            overlay_resized = overlay_img.resize((w_px, h_px))
            background.paste(overlay_resized, (x_px, y_px), overlay_resized)

            y_pt -= (h_pt + gap_pt)
            if y_pt < margin_pt:
                break

    buf = io.BytesIO()
    fmt_norm = fmt.upper()
    if fmt_norm in {"JPG", "JPEG"}:
        background.save(buf, format="JPEG", quality=92, optimize=True)
        ext = "jpg"
    else:
        background.save(buf, format="PNG", optimize=True)
        ext = "png"

    buf.seek(0)
    return ContentFile(buf.read(), name=f"{certificate.id}.{ext}")
