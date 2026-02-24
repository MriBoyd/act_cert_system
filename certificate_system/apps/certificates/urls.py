from django.contrib.auth import views as auth_views
from django.urls import path

from apps.certificates.views import admin_views, integration_api_views, public_views
from apps.certificates.views.api_views import VerifyCertificateAPIView

urlpatterns = [
    path("", public_views.verification_home, name="public-verify"),
    path("qr-tools/", public_views.qr_tools, name="public-qr-tools"),
    path("verify/<uuid:certificate_uuid>/", public_views.verify_by_uuid, name="public-verify-detail"),
    path("api/verify/<uuid:certificate_uuid>/", VerifyCertificateAPIView.as_view(), name="api-verify-certificate"),
    path(
        "api/integration/templates/",
        integration_api_views.IntegrationTemplateListAPIView.as_view(),
        name="api-integration-templates",
    ),
    path(
        "api/integration/templates/<uuid:template_uuid>/",
        integration_api_views.IntegrationTemplateDetailAPIView.as_view(),
        name="api-integration-template-detail",
    ),
    path(
        "api/integration/certificates/",
        integration_api_views.IntegrationCertificateCreateAPIView.as_view(),
        name="api-integration-certificate-create",
    ),
    path(
        "api/integration/certificates/bulk/",
        integration_api_views.IntegrationCertificateBulkCreateAPIView.as_view(),
        name="api-integration-certificate-bulk",
    ),
    path(
        "api/integration/certificates/<uuid:certificate_uuid>/",
        integration_api_views.IntegrationCertificateDetailAPIView.as_view(),
        name="api-integration-certificate-detail",
    ),
    path(
        "api/integration/certificates/<uuid:certificate_uuid>/status/",
        integration_api_views.IntegrationCertificateStatusAPIView.as_view(),
        name="api-integration-certificate-status",
    ),
    path(
        "api/integration/certificates/<uuid:certificate_uuid>/download/pdf/",
        integration_api_views.IntegrationCertificatePdfDownloadAPIView.as_view(),
        name="api-integration-certificate-pdf",
    ),
    path(
        "api/integration/certificates/<uuid:certificate_uuid>/download/png/",
        integration_api_views.IntegrationCertificatePngDownloadAPIView.as_view(),
        name="api-integration-certificate-png",
    ),
    path(
        "api/integration/certificates/<uuid:certificate_uuid>/download/jpg/",
        integration_api_views.IntegrationCertificateJpgDownloadAPIView.as_view(),
        name="api-integration-certificate-jpg",
    ),
    path(
        "api/integration/certificates/<uuid:certificate_uuid>/download/qr/",
        integration_api_views.IntegrationCertificateQrDownloadAPIView.as_view(),
        name="api-integration-certificate-qr",
    ),
    path("login/", auth_views.LoginView.as_view(template_name="admin/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("admin/dashboard/", admin_views.dashboard, name="admin-dashboard"),
    path("admin/feature-flags/", admin_views.feature_flags_management, name="admin-feature-flags"),
    path("admin/certificates/", admin_views.certificate_list, name="admin-certificate-list"),
    path("admin/templates/", admin_views.template_list, name="admin-template-list"),
    path(
        "admin/certificates/<uuid:certificate_uuid>/",
        admin_views.certificate_detail,
        name="admin-certificate-detail",
    ),
    path(
        "admin/certificates/<uuid:certificate_uuid>/delete/",
        admin_views.delete_certificate,
        name="admin-certificate-delete",
    ),
    path("admin/templates/create/", admin_views.create_template, name="admin-create-template"),
    path("admin/templates/<uuid:template_uuid>/edit/", admin_views.edit_template, name="admin-edit-template"),
    path(
        "admin/templates/<uuid:template_uuid>/delete/",
        admin_views.delete_template,
        name="admin-template-delete",
    ),
    path(
        "admin/templates/<uuid:template_uuid>/toggle/",
        admin_views.toggle_template_status,
        name="admin-toggle-template-status",
    ),
    path("admin/certificates/generate/", admin_views.generate_certificate_view, name="admin-generate-certificate"),
    path("admin/certificates/bulk/", admin_views.bulk_generate_certificates, name="admin-bulk-generate"),
    path(
        "admin/certificates/<uuid:certificate_uuid>/download/pdf/",
        admin_views.download_certificate_pdf,
        name="admin-download-certificate-pdf",
    ),
    path(
        "admin/certificates/<uuid:certificate_uuid>/download/png/",
        admin_views.download_certificate_png,
        name="admin-download-certificate-png",
    ),
    path(
        "admin/certificates/<uuid:certificate_uuid>/download/jpg/",
        admin_views.download_certificate_jpg,
        name="admin-download-certificate-jpg",
    ),
    path(
        "admin/certificates/<uuid:certificate_uuid>/download/qr/",
        admin_views.download_certificate_qr,
        name="admin-download-certificate-qr",
    ),
    path(
        "admin/certificates/<uuid:certificate_uuid>/status/",
        admin_views.manage_certificate_status,
        name="admin-certificate-status",
    ),
    path("admin/logs/", admin_views.log_management, name="admin-log-management"),
    path(
        "admin/logs/<str:log_key>/download/",
        admin_views.download_log_file,
        name="admin-log-download",
    ),
    path(
        "admin/logs/<str:log_key>/clear/",
        admin_views.clear_log_file,
        name="admin-log-clear",
    ),
]
