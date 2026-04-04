from datetime import date
from functools import wraps
import logging
from pathlib import Path
from typing import Final
import uuid

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.conf import settings
from django.db.models import Count, Q
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.http import FileResponse, Http404, HttpResponse
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from apps.certificates.forms import (
    BulkCertificateUploadForm,
    CertificateGenerateForm,
    CertificateStatusForm,
    CertificateTemplateForm,
)
from apps.certificates.feature_flags import DEFAULT_FLAGS, require_feature
from apps.certificates.models import Certificate, CertificateTemplate, FeatureFlagOverride, VerificationLog
from apps.certificates.services.certificate_service import (
    DuplicateCertificateError,
    create_certificate,
)
from apps.certificates.services.image_generator import generate_certificate_image


audit_logger = logging.getLogger("audit")
security_logger = logging.getLogger("security")


def _delete_storage_files(*file_fields) -> None:
    for file_field in file_fields:
        try:
            if file_field:
                file_field.delete(save=False)
        except Exception:  # noqa: BLE001
            # Best-effort cleanup.
            pass


LOG_FILES: Final[dict[str, str]] = {
    "app": "app.log",
    "security": "security.log",
    "audit": "audit.log",
    "access": "access.log",
}


def _safe_log_path(log_key: str) -> Path:
    if log_key not in LOG_FILES:
        raise Http404("Invalid log.")
    return Path(settings.LOG_DIR) / LOG_FILES[log_key]


def _tail_text(file_path: Path, lines: int, max_bytes: int = 1024 * 1024) -> str:
    if lines <= 0:
        return ""
    if not file_path.exists() or not file_path.is_file():
        return ""

    try:
        with file_path.open("rb") as file:
            file.seek(0, 2)
            size = file.tell()
            read_size = min(size, max_bytes)
            file.seek(size - read_size)
            data = file.read(read_size)
    except OSError:
        return ""

    text = data.decode("utf-8", errors="replace")
    parts = text.splitlines()
    return "\n".join(parts[-lines:])


def _read_recent_lines(file_path: Path, max_bytes: int = 1024 * 1024) -> list[str]:
    if not file_path.exists() or not file_path.is_file():
        return []

    try:
        with file_path.open("rb") as file:
            file.seek(0, 2)
            size = file.tell()
            read_size = min(size, max_bytes)
            file.seek(size - read_size)
            data = file.read(read_size)
    except OSError:
        return []

    text = data.decode("utf-8", errors="replace")
    return text.splitlines()


def certificate_admin_required(view_func):
    @staff_member_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)

        allowed_roles = {"SUPER_ADMIN", "CERTIFICATE_ADMIN"}
        if getattr(request.user, "role", None) not in allowed_roles:
            security_logger.warning(
                "event=admin_access_denied username=%s role=%s",
                getattr(request.user, "get_username", lambda: "")(),
                getattr(request.user, "role", None),
            )
            messages.error(request, "You do not have permission to access this page.")
            return redirect("public-verify")
        return view_func(request, *args, **kwargs)

    return _wrapped


@certificate_admin_required
@require_feature("admin_dashboard")
def dashboard(request):
    context = {
        "total_templates": CertificateTemplate.objects.count(),
        "total_certificates": Certificate.objects.count(),
        "valid_certificates": Certificate.objects.filter(status=Certificate.Status.VALID, is_enabled=True).count(),
        "revoked_certificates": Certificate.objects.filter(status=Certificate.Status.REVOKED).count(),
        "recent_logs": VerificationLog.objects.select_related("certificate")[:10],
        "recent_certificates": Certificate.objects.select_related("template", "issued_by")[:8],
        "certificates_by_course": (
            Certificate.objects.values("course_name")
            .annotate(total=Count("id"))
            .order_by("-total")[:5]
        ),
    }
    return render(request, "admin/dashboard.html", context)


@certificate_admin_required
def feature_flags_management(request):
    if not request.user.is_superuser:
        messages.error(request, "Only superusers can manage feature flags.")
        return redirect("admin-dashboard")

    if request.method == "POST":
        name = (request.POST.get("name") or "").strip()
        state = (request.POST.get("state") or "").strip()

        if name not in DEFAULT_FLAGS:
            messages.error(request, "Unknown feature flag.")
            return redirect("admin-feature-flags")

        if state == "inherit":
            FeatureFlagOverride.objects.filter(name=name).delete()
            audit_logger.info(
                "event=feature_flag_override_deleted name=%s by=%s",
                name,
                request.user.get_username(),
            )
            messages.success(request, f"{name} reverted to default.")
            return redirect("admin-feature-flags")

        if state not in {"on", "off"}:
            messages.error(request, "Invalid state.")
            return redirect("admin-feature-flags")

        enabled = state == "on"
        FeatureFlagOverride.objects.update_or_create(
            name=name,
            defaults={
                "enabled": enabled,
                "updated_by": request.user,
            },
        )
        audit_logger.info(
            "event=feature_flag_override_set name=%s enabled=%s by=%s",
            name,
            enabled,
            request.user.get_username(),
        )
        messages.success(request, f"{name} set to {'ON' if enabled else 'OFF'}.")
        return redirect("admin-feature-flags")

    overrides = {o.name: o for o in FeatureFlagOverride.objects.all()}

    rows = []
    settings_flags = getattr(settings, "FEATURE_FLAGS", {})
    for name in sorted(DEFAULT_FLAGS.keys()):
        override = overrides.get(name)
        if override is not None:
            effective = override.enabled
            source = "db"
            state = "on" if override.enabled else "off"
        elif name in settings_flags:
            effective = bool(settings_flags.get(name))
            source = "env"
            state = "inherit"
        else:
            effective = bool(DEFAULT_FLAGS.get(name, False))
            source = "default"
            state = "inherit"

        rows.append(
            {
                "name": name,
                "effective": effective,
                "source": source,
                "state": state,
                "override": override,
            }
        )

    return render(request, "admin/feature_flags.html", {"rows": rows})


@certificate_admin_required
@require_feature("template_management")
def create_template(request):
    if request.method == "POST":
        form = CertificateTemplateForm(request.POST, request.FILES)
        if form.is_valid():
            template = form.save()
            audit_logger.info(
                "event=template_created template_id=%s name=%s",
                template.id,
                template.name,
            )
            messages.success(request, "Certificate template created successfully.")
            return redirect("admin-template-list")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.replace('_', ' ').title()}: {error}")
    else:
        form = CertificateTemplateForm()

    return render(
        request,
        "admin/template_form.html",
        {"form": form, "is_edit": False},
    )


@certificate_admin_required
@require_feature("template_management")
def template_list(request):
    search = request.GET.get("search", "").strip()
    active_filter = request.GET.get("active", "")
    sort_by = request.GET.get("sort", "created_at")
    sort_dir = request.GET.get("dir", "desc")

    try:
        per_page = int(request.GET.get("per_page", 25))
    except (TypeError, ValueError):
        per_page = 25

    if per_page not in {10, 25, 50, 100}:
        per_page = 25

    sortable_fields = {
        "name": "name",
        "issuer_name": "issuer_name",
        "is_active": "is_active",
        "total_certificates": "total_certificates",
        "created_at": "created_at",
    }
    if sort_by not in sortable_fields:
        sort_by = "created_at"
    if sort_dir not in {"asc", "desc"}:
        sort_dir = "desc"

    order_field = sortable_fields[sort_by]
    if sort_dir == "desc":
        order_field = f"-{order_field}"

    templates = CertificateTemplate.objects.annotate(total_certificates=Count("certificates"))
    if search:
        templates = templates.filter(
            Q(name__icontains=search) | Q(issuer_name__icontains=search)
        )
    if active_filter in {"true", "false"}:
        templates = templates.filter(is_active=(active_filter == "true"))

    templates = templates.order_by(order_field, "-created_at")

    paginator = Paginator(templates, per_page)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()
    query_params.pop("page", None)
    querystring = query_params.urlencode()

    sort_query_params = request.GET.copy()
    sort_query_params.pop("sort", None)
    sort_query_params.pop("dir", None)
    sort_query_params.pop("page", None)
    sort_querystring = sort_query_params.urlencode()

    return render(
        request,
        "admin/template_list.html",
        {
            "templates": page_obj.object_list,
            "page_obj": page_obj,
            "paginator": paginator,
            "querystring": querystring,
            "sort_querystring": sort_querystring,
            "search": search,
            "active_filter": active_filter,
            "per_page": per_page,
            "sort_by": sort_by,
            "sort_dir": sort_dir,
        },
    )


@certificate_admin_required
@require_feature("template_management")
def edit_template(request, template_uuid):
    template = get_object_or_404(CertificateTemplate, id=template_uuid)

    if request.method == "POST":
        form = CertificateTemplateForm(request.POST, request.FILES, instance=template)
        if form.is_valid():
            form.save()
            audit_logger.info(
                "event=template_updated template_id=%s name=%s",
                template.id,
                template.name,
            )
            messages.success(request, "Template updated successfully.")
            return redirect("admin-template-list")
    else:
        form = CertificateTemplateForm(instance=template)

    return render(
        request,
        "admin/template_form.html",
        {
            "form": form,
            "is_edit": True,
            "template_obj": template,
        },
    )


@certificate_admin_required
@require_feature("template_management")
def toggle_template_status(request, template_uuid):
    if request.method != "POST":
        return redirect("admin-template-list")

    template = get_object_or_404(CertificateTemplate, id=template_uuid)
    template.is_active = not template.is_active
    template.save(update_fields=["is_active", "updated_at"])

    audit_logger.info(
        "event=template_status_toggled template_id=%s is_active=%s by=%s",
        template.id,
        template.is_active,
        request.user.get_username(),
    )

    status_text = "activated" if template.is_active else "deactivated"
    messages.success(request, f"Template {status_text} successfully.")
    return redirect("admin-template-list")


@certificate_admin_required
@require_feature("template_management")
def bulk_template_actions(request):
    if request.method != "POST":
        return redirect("admin-template-list")

    next_url = request.POST.get("next") or reverse("admin-template-list")
    if not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = reverse("admin-template-list")

    action = (request.POST.get("action") or "").strip()
    raw_ids = request.POST.getlist("selected_ids")

    allowed_actions = {"activate", "deactivate", "delete"}
    if action not in allowed_actions:
        messages.error(request, "Invalid bulk action.")
        return redirect(next_url)

    if not raw_ids:
        messages.error(request, "Select at least one template.")
        return redirect(next_url)

    selected_ids: list[uuid.UUID] = []
    for raw_id in raw_ids:
        try:
            selected_ids.append(uuid.UUID(str(raw_id)))
        except (TypeError, ValueError):
            continue

    if not selected_ids:
        messages.error(request, "No valid template IDs selected.")
        return redirect(next_url)

    qs = CertificateTemplate.objects.filter(id__in=selected_ids)
    total = qs.count()
    if total == 0:
        messages.error(request, "No matching templates found.")
        return redirect(next_url)

    now = timezone.now()
    username = request.user.get_username()

    if action == "activate":
        updated = qs.update(is_active=True, updated_at=now)
        messages.success(request, f"Activated {updated} template(s).")
        audit_logger.info(
            "event=bulk_template_activate requested=%s updated=%s by=%s",
            total,
            updated,
            username,
        )
        return redirect(next_url)

    if action == "deactivate":
        updated = qs.update(is_active=False, updated_at=now)
        messages.success(request, f"Deactivated {updated} template(s).")
        audit_logger.info(
            "event=bulk_template_deactivate requested=%s updated=%s by=%s",
            total,
            updated,
            username,
        )
        return redirect(next_url)

    # action == "delete"
    templates = list(qs.only("id", "name", "background_image"))
    files_to_cleanup = []
    skipped_in_use = 0
    deleted = 0

    with transaction.atomic():
        for template in templates:
            if template.certificates.exists():
                skipped_in_use += 1
                continue

            files_to_cleanup.append((template.background_image,))
            template.delete()
            deleted += 1

        def _cleanup_all():
            for batch in files_to_cleanup:
                _delete_storage_files(*batch)

        transaction.on_commit(_cleanup_all)

    if deleted:
        messages.success(request, f"Deleted {deleted} template(s) and cleaned up background images.")
    if skipped_in_use:
        messages.warning(request, f"Skipped {skipped_in_use} template(s) currently in use.")
    audit_logger.info(
        "event=bulk_template_delete requested=%s deleted=%s skipped_in_use=%s by=%s",
        total,
        deleted,
        skipped_in_use,
        username,
    )
    return redirect(next_url)


@certificate_admin_required
@require_feature("certificate_management")
def bulk_certificate_actions(request):
    if request.method != "POST":
        return redirect("admin-certificate-list")

    next_url = request.POST.get("next") or reverse("admin-certificate-list")
    if not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = reverse("admin-certificate-list")

    action = (request.POST.get("action") or "").strip()
    raw_ids = request.POST.getlist("selected_ids")

    allowed_actions = {
        "enable",
        "disable",
        "mark_valid",
        "mark_revoked",
        "mark_disabled",
        "delete",
    }
    if action not in allowed_actions:
        messages.error(request, "Invalid bulk action.")
        return redirect(next_url)

    if not raw_ids:
        messages.error(request, "Select at least one certificate.")
        return redirect(next_url)

    selected_ids: list[uuid.UUID] = []
    for raw_id in raw_ids:
        try:
            selected_ids.append(uuid.UUID(str(raw_id)))
        except (TypeError, ValueError):
            continue

    if not selected_ids:
        messages.error(request, "No valid certificate IDs selected.")
        return redirect(next_url)

    qs = Certificate.objects.filter(id__in=selected_ids)
    total = qs.count()
    if total == 0:
        messages.error(request, "No matching certificates found.")
        return redirect(next_url)

    now = timezone.now()
    username = request.user.get_username()

    if action == "enable":
        updated = qs.filter(status=Certificate.Status.VALID).update(is_enabled=True, updated_at=now)
        skipped = total - updated
        if updated:
            messages.success(request, f"Enabled {updated} certificate(s).")
        if skipped:
            messages.warning(request, f"Skipped {skipped} non-VALID certificate(s).")
        audit_logger.info(
            "event=bulk_certificate_enable requested=%s updated=%s skipped=%s by=%s",
            total,
            updated,
            skipped,
            username,
        )
        return redirect(next_url)

    if action == "disable":
        updated = qs.update(is_enabled=False, updated_at=now)
        messages.success(request, f"Disabled {updated} certificate(s).")
        audit_logger.info(
            "event=bulk_certificate_disable requested=%s updated=%s by=%s",
            total,
            updated,
            username,
        )
        return redirect(next_url)

    if action == "mark_valid":
        updated = qs.update(status=Certificate.Status.VALID, updated_at=now)
        messages.success(request, f"Marked {updated} certificate(s) as VALID.")
        audit_logger.info(
            "event=bulk_certificate_mark_valid requested=%s updated=%s by=%s",
            total,
            updated,
            username,
        )
        return redirect(next_url)

    if action == "mark_revoked":
        updated = qs.update(status=Certificate.Status.REVOKED, is_enabled=False, updated_at=now)
        messages.success(request, f"Revoked {updated} certificate(s).")
        audit_logger.info(
            "event=bulk_certificate_mark_revoked requested=%s updated=%s by=%s",
            total,
            updated,
            username,
        )
        return redirect(next_url)

    if action == "mark_disabled":
        updated = qs.update(status=Certificate.Status.DISABLED, is_enabled=False, updated_at=now)
        messages.success(request, f"Marked {updated} certificate(s) as DISABLED.")
        audit_logger.info(
            "event=bulk_certificate_mark_disabled requested=%s updated=%s by=%s",
            total,
            updated,
            username,
        )
        return redirect(next_url)

    # action == "delete"
    certs = list(
        qs.only(
            "id",
            "serial_number",
            "pdf_file",
            "qr_code_image",
            "png_file",
            "jpg_file",
            "logo_image",
            "signature_image",
        )
    )
    cert_overlay_files = {
        c.id: [oi.image for oi in c.overlay_images.all()]
        for c in Certificate.objects.filter(id__in=[c.id for c in certs]).prefetch_related("overlay_images")
    }
    files_to_cleanup: list[tuple] = []
    deleted = 0
    with transaction.atomic():
        for cert in certs:
            files_to_cleanup.append(
                (
                    cert.pdf_file,
                    cert.qr_code_image,
                    getattr(cert, "png_file", None),
                    getattr(cert, "jpg_file", None),
                    getattr(cert, "logo_image", None),
                    getattr(cert, "signature_image", None),
                )
            )
            cert.delete()
            deleted += 1

        def _cleanup_all():
            for batch in files_to_cleanup:
                _delete_storage_files(*batch)

            for overlay_list in cert_overlay_files.values():
                _delete_storage_files(*overlay_list)

        transaction.on_commit(_cleanup_all)

    messages.success(request, f"Deleted {deleted} certificate(s) and cleaned up files.")
    audit_logger.info(
        "event=bulk_certificate_delete requested=%s deleted=%s by=%s",
        total,
        deleted,
        username,
    )
    return redirect(next_url)


@certificate_admin_required
@require_feature("certificate_management")
def delete_certificate(request, certificate_uuid):
    if request.method != "POST":
        return redirect("admin-certificate-detail", certificate_uuid=certificate_uuid)

    cert = get_object_or_404(Certificate, id=certificate_uuid)

    pdf_file = cert.pdf_file
    qr_file = cert.qr_code_image
    png_file = getattr(cert, "png_file", None)
    jpg_file = getattr(cert, "jpg_file", None)
    logo_file = getattr(cert, "logo_image", None)
    signature_file = getattr(cert, "signature_image", None)
    overlay_files = [oi.image for oi in cert.overlay_images.all()]

    cert_serial = cert.serial_number
    cert_id = str(cert.id)

    with transaction.atomic():
        cert.delete()

        def _cleanup():
            _delete_storage_files(pdf_file, qr_file, png_file, jpg_file, logo_file, signature_file)
            _delete_storage_files(*overlay_files)

        transaction.on_commit(_cleanup)

    audit_logger.info(
        "event=certificate_deleted certificate_id=%s serial=%s by=%s",
        cert_id,
        cert_serial,
        request.user.get_username(),
    )
    messages.success(request, "Certificate deleted successfully.")
    return redirect("admin-certificate-list")


@certificate_admin_required
@require_feature("template_management")
def delete_template(request, template_uuid):
    if request.method != "POST":
        return redirect("admin-template-list")

    template = get_object_or_404(CertificateTemplate, id=template_uuid)

    if template.certificates.exists():
        messages.error(request, "Template is in use and cannot be deleted.")
        return redirect("admin-template-list")

    bg = template.background_image
    template_name = template.name
    template_id = str(template.id)

    with transaction.atomic():
        template.delete()

        def _cleanup():
            _delete_storage_files(bg)

        transaction.on_commit(_cleanup)

    audit_logger.info(
        "event=template_deleted template_id=%s name=%s by=%s",
        template_id,
        template_name,
        request.user.get_username(),
    )
    messages.success(request, "Template deleted successfully.")
    return redirect("admin-template-list")


@certificate_admin_required
@require_feature("certificate_generation")
def generate_certificate_view(request):
    if request.method == "POST":
        form = CertificateGenerateForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                certificate = create_certificate(
                    template=form.cleaned_data["template"],
                    issued_by=request.user,
                    recipient_name=form.cleaned_data["recipient_name"],
                    recipient_email=form.cleaned_data["recipient_email"],
                    course_name=form.cleaned_data["course_name"],
                    issue_date=form.cleaned_data["issue_date"],
                    serial_number=form.cleaned_data["serial_number"],
                    logo_image=form.cleaned_data.get("logo_image"),
                    signature_image=form.cleaned_data.get("signature_image"),
                    extra_images=form.cleaned_data.get("extra_images") or [],
                )
                audit_logger.info(
                    "event=certificate_generated certificate_id=%s serial=%s template_id=%s",
                    certificate.id,
                    certificate.serial_number,
                    certificate.template_id,
                )
                messages.success(request, f"Certificate generated with ID: {certificate.id}")
                return redirect("admin-dashboard")
            except DuplicateCertificateError as exc:
                messages.error(request, str(exc))
    else:
        form = CertificateGenerateForm()

    return render(request, "admin/generate_certificate.html", {"form": form})


@certificate_admin_required
@require_feature("bulk_generation")
def bulk_generate_certificates(request):
    if request.method == "POST":
        form = BulkCertificateUploadForm(request.POST, request.FILES)
        if form.is_valid():
            rows = form.parse_rows()
            template = form.cleaned_data["template"]
            success_count = 0
            errors = []
            for index, row in enumerate(rows, start=1):
                try:
                    issue_date = date.fromisoformat(row["issue_date"])
                    create_certificate(
                        template=template,
                        issued_by=request.user,
                        recipient_name=row["recipient_name"],
                        recipient_email=row.get("recipient_email", ""),
                        course_name=row["course_name"],
                        issue_date=issue_date,
                        serial_number=row["serial_number"],
                    )
                    success_count += 1
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"Row {index}: {exc}")

            audit_logger.info(
                "event=bulk_generate_completed template_id=%s rows=%s success=%s errors=%s",
                template.id,
                len(rows),
                success_count,
                len(errors),
            )

            if success_count:
                messages.success(request, f"Generated {success_count} certificates.")
            for error in errors[:10]:
                messages.error(request, error)
            return redirect("admin-dashboard")
    else:
        form = BulkCertificateUploadForm()

    return render(request, "admin/bulk_upload.html", {"form": form})


@certificate_admin_required
@require_feature("certificate_management")
def manage_certificate_status(request, certificate_uuid):
    certificate = get_object_or_404(Certificate, id=certificate_uuid)
    old_status = certificate.status
    old_enabled = certificate.is_enabled

    if request.method == "POST":
        form = CertificateStatusForm(request.POST, instance=certificate)
        if form.is_valid():
            updated = form.save()
            audit_logger.info(
                "event=certificate_status_changed certificate_id=%s serial=%s old_status=%s new_status=%s old_enabled=%s new_enabled=%s",
                updated.id,
                updated.serial_number,
                old_status,
                updated.status,
                old_enabled,
                updated.is_enabled,
            )
            messages.success(request, "Certificate status updated.")
            return redirect("admin-dashboard")
    else:
        form = CertificateStatusForm(instance=certificate)

    return render(request, "admin/certificate_status.html", {"form": form, "certificate": certificate})


from apps.certificates.services.verification import verify_certificate, _extract_ip


@certificate_admin_required
@require_feature("certificate_detail")
def certificate_detail(request, certificate_uuid):
    certificate = get_object_or_404(
        Certificate.objects.select_related("template", "issued_by").prefetch_related("overlay_images"),
        id=certificate_uuid,
    )
    # Verification check WITHOUT tracking it as a real "hit"
    _, is_valid = verify_certificate(
        certificate_uuid, 
        request, 
        track=False, 
        source=VerificationLog.Source.ADMIN
    )
    
    # Only show real verification logs (excluded system/admin previews)
    verification_logs = certificate.verification_logs.exclude(
        source=VerificationLog.Source.ADMIN
    )[:20]

    return render(
        request,
        "admin/certificate_detail.html",
        {
            "certificate": certificate,
            "verification_logs": verification_logs,
            "is_valid": is_valid,
        },
    )


@certificate_admin_required
@require_feature("certificate_management")
def certificate_list(request):
    status_filter = request.GET.get("status", "")
    enabled_filter = request.GET.get("enabled", "")
    template_filter = request.GET.get("template", "")
    issuer_filter = request.GET.get("issuer", "")
    date_from = request.GET.get("date_from", "")
    date_to = request.GET.get("date_to", "")
    search = request.GET.get("search", "").strip()
    sort_by = request.GET.get("sort", "created_at")
    sort_dir = request.GET.get("dir", "desc")

    try:
        per_page = int(request.GET.get("per_page", 25))
    except (TypeError, ValueError):
        per_page = 25

    if per_page not in {10, 25, 50, 100}:
        per_page = 25

    sortable_fields = {
        "recipient_name": "recipient_name",
        "course_name": "course_name",
        "serial_number": "serial_number",
        "issue_date": "issue_date",
        "status": "status",
        "created_at": "created_at",
    }
    if sort_by not in sortable_fields:
        sort_by = "created_at"
    if sort_dir not in {"asc", "desc"}:
        sort_dir = "desc"

    order_field = sortable_fields[sort_by]
    if sort_dir == "desc":
        order_field = f"-{order_field}"

    certificates = (
        Certificate.objects.select_related("template", "issued_by")
        .defer(
            "metadata",
            "pdf_file",
            "qr_code_image",
            "png_file",
            "jpg_file",
            "logo_image",
            "signature_image",
        )
        .order_by(order_field, "-created_at")
    )

    if status_filter:
        certificates = certificates.filter(status=status_filter)
    if enabled_filter in {"true", "false"}:
        certificates = certificates.filter(is_enabled=(enabled_filter == "true"))
    if template_filter:
        certificates = certificates.filter(template_id=template_filter)
    if issuer_filter:
        certificates = certificates.filter(issued_by_id=issuer_filter)
    if date_from:
        certificates = certificates.filter(issue_date__gte=date_from)
    if date_to:
        certificates = certificates.filter(issue_date__lte=date_to)
    if search:
        certificates = certificates.filter(
            Q(recipient_name__icontains=search)
            | Q(serial_number__icontains=search)
            | Q(course_name__icontains=search)
        )

    paginator = Paginator(certificates, per_page)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()
    query_params.pop("page", None)
    querystring = query_params.urlencode()

    sort_query_params = request.GET.copy()
    sort_query_params.pop("sort", None)
    sort_query_params.pop("dir", None)
    sort_query_params.pop("page", None)
    sort_querystring = sort_query_params.urlencode()

    templates = CertificateTemplate.objects.filter(is_active=True).only("id", "name").order_by("name")
    issuers = (
        Certificate.objects.select_related("issued_by")
        .values("issued_by_id", "issued_by__username")
        .distinct()
        .order_by("issued_by__username")
    )

    return render(
        request,
        "admin/certificate_list.html",
        {
            "certificates": page_obj.object_list,
            "page_obj": page_obj,
            "paginator": paginator,
            "status_filter": status_filter,
            "enabled_filter": enabled_filter,
            "template_filter": template_filter,
            "issuer_filter": issuer_filter,
            "date_from": date_from,
            "date_to": date_to,
            "search": search,
            "per_page": per_page,
            "sort_by": sort_by,
            "sort_dir": sort_dir,
            "sort_querystring": sort_querystring,
            "querystring": querystring,
            "status_choices": Certificate.Status.choices,
            "templates": templates,
            "issuers": issuers,
        },
    )


@certificate_admin_required
@require_feature("certificate_download")
def download_certificate_pdf(request, certificate_uuid):
    certificate = get_object_or_404(Certificate, id=certificate_uuid)
    if not certificate.pdf_file:
        raise Http404("Certificate PDF not available.")

    audit_logger.info(
        "event=certificate_pdf_download certificate_id=%s serial=%s",
        certificate.id,
        certificate.serial_number,
    )

    return FileResponse(
        certificate.pdf_file.open("rb"),
        as_attachment=True,
        filename=f"certificate-{certificate.serial_number}.pdf",
    )


@certificate_admin_required
@require_feature("certificate_download")
def download_certificate_qr(request, certificate_uuid):
    certificate = get_object_or_404(Certificate, id=certificate_uuid)
    if not certificate.qr_code_image:
        raise Http404("Certificate QR not available.")

    audit_logger.info(
        "event=certificate_qr_download certificate_id=%s serial=%s",
        certificate.id,
        certificate.serial_number,
    )

    return FileResponse(
        certificate.qr_code_image.open("rb"),
        as_attachment=True,
        filename=f"certificate-{certificate.serial_number}-qr.png",
    )


@certificate_admin_required
@require_feature("certificate_download")
def download_certificate_png(request, certificate_uuid):
    certificate = get_object_or_404(Certificate, id=certificate_uuid)

    audit_logger.info(
        "event=certificate_png_download certificate_id=%s serial=%s",
        certificate.id,
        certificate.serial_number,
    )

    if getattr(certificate, "png_file", None):
        return FileResponse(
            certificate.png_file.open("rb"),
            as_attachment=True,
            filename=f"certificate-{certificate.serial_number}.png",
            content_type="image/png",
        )

    image_file = generate_certificate_image(certificate, fmt="PNG")
    certificate.png_file.save(image_file.name, image_file, save=True)
    return FileResponse(
        certificate.png_file.open("rb"),
        as_attachment=True,
        filename=f"certificate-{certificate.serial_number}.png",
        content_type="image/png",
    )


@certificate_admin_required
@require_feature("certificate_download")
def download_certificate_jpg(request, certificate_uuid):
    certificate = get_object_or_404(Certificate, id=certificate_uuid)

    audit_logger.info(
        "event=certificate_jpg_download certificate_id=%s serial=%s",
        certificate.id,
        certificate.serial_number,
    )

    if getattr(certificate, "jpg_file", None):
        return FileResponse(
            certificate.jpg_file.open("rb"),
            as_attachment=True,
            filename=f"certificate-{certificate.serial_number}.jpg",
            content_type="image/jpeg",
        )

    image_file = generate_certificate_image(certificate, fmt="JPEG")
    certificate.jpg_file.save(image_file.name, image_file, save=True)
    return FileResponse(
        certificate.jpg_file.open("rb"),
        as_attachment=True,
        filename=f"certificate-{certificate.serial_number}.jpg",
        content_type="image/jpeg",
    )


@certificate_admin_required
def access_analytics(request):
    """Business-focused view for tracking certificate access/verification attempts."""
    query = request.GET.get("q", "").strip()
    source_filter = request.GET.get("source", "").strip()
    valid_filter = request.GET.get("valid", "").strip()
    sort = request.GET.get("sort", "-checked_at")

    logs = VerificationLog.objects.select_related("certificate").all()

    # Exclude admin internal checks by default to keep it focused on external traffic
    logs = logs.exclude(source=VerificationLog.Source.ADMIN)

    if query:
        logs = logs.filter(
            Q(certificate__recipient_name__icontains=query) |
            Q(certificate__serial_number__icontains=query) |
            Q(certificate_uuid__icontains=query) |
            Q(requester_ip__icontains=query)
        )

    if source_filter:
        logs = logs.filter(source=source_filter)

    if valid_filter in ["1", "0"]:
        logs = logs.filter(is_valid=(valid_filter == "1"))

    # Sorting
    allowed_sorts = ["checked_at", "-checked_at", "source", "is_valid", "certificate__recipient_name"]
    if sort not in allowed_sorts:
        sort = "-checked_at"
    logs = logs.order_by(sort)

    paginator = Paginator(logs, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    sources = VerificationLog.Source.choices

    return render(
        request,
        "admin/access_analytics.html",
        {
            "page_obj": page_obj,
            "q": query,
            "source_filter": source_filter,
            "valid_filter": valid_filter,
            "sort": sort,
            "sources": sources,
        },
    )


@certificate_admin_required
@require_feature("log_management")
def log_management(request):
    log_key = request.GET.get("log", "app").strip().lower()
    if log_key not in LOG_FILES:
        log_key = "app"

    query = request.GET.get("q", "").strip()

    try:
        lines = int(request.GET.get("lines", 200))
    except (TypeError, ValueError):
        lines = 200
    lines = max(50, min(lines, 2000))

    try:
        page = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    page = max(1, page)

    file_path = _safe_log_path(log_key)

    recent_lines = _read_recent_lines(file_path)
    if query:
        needle = query.lower()
        recent_lines = [ln for ln in recent_lines if needle in ln.lower()]

    total_lines = len(recent_lines)
    total_pages = max(1, (total_lines + lines - 1) // lines)
    if page > total_pages:
        page = total_pages

    end = total_lines - (page - 1) * lines
    start = max(0, end - lines)
    page_lines = [ln.strip() for ln in recent_lines[start:end]] if end > 0 else []
    content = "\n".join(page_lines)

    query_params = request.GET.copy()
    query_params.pop("page", None)
    querystring = query_params.urlencode()

    file_info = None
    if file_path.exists() and file_path.is_file():
        stat = file_path.stat()
        file_info = {
            "name": file_path.name,
            "size": stat.st_size,
            "modified": timezone.datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.get_current_timezone()
            ),
        }

    return render(
        request,
        "admin/log_management.html",
        {
            "log_key": log_key,
            "log_files": LOG_FILES,
            "lines": lines,
            "q": query,
            "page": page,
            "total_pages": total_pages,
            "total_lines": total_lines,
            "querystring": querystring,
            "content": content,
            "file_info": file_info,
            "can_clear": bool(getattr(request.user, "is_superuser", False)),
        },
    )


@certificate_admin_required
@require_feature("log_management")
def download_log_file(request, log_key: str):
    file_path = _safe_log_path(log_key)
    if not file_path.exists() or not file_path.is_file():
        raise Http404("Log not found.")

    audit_logger.info("event=log_download log=%s", log_key)
    return FileResponse(
        file_path.open("rb"),
        as_attachment=True,
        filename=file_path.name,
    )


@certificate_admin_required
@require_feature("log_management")
def clear_log_file(request, log_key: str):
    if request.method != "POST":
        return redirect("admin-log-management")

    if not getattr(request.user, "is_superuser", False):
        messages.error(request, "Only superusers can clear logs.")
        security_logger.warning(
            "event=log_clear_denied username=%s log=%s",
            getattr(request.user, "get_username", lambda: "")(),
            log_key,
        )
        return redirect("admin-log-management")

    file_path = _safe_log_path(log_key)
    log_return_url = f"{reverse('admin-log-management')}?log={log_key}"
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("w", encoding="utf-8"):
            pass
    except OSError:
        messages.error(request, "Failed to clear log.")
        return redirect(log_return_url)

    audit_logger.info("event=log_cleared log=%s", log_key)
    messages.success(request, "Log cleared.")
    return redirect(log_return_url)
