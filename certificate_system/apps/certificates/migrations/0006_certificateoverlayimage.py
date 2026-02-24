from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    dependencies = [
        ("certificates", "0005_certificate_logo_signature_images"),
    ]

    operations = [
        migrations.CreateModel(
            name="CertificateOverlayImage",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("name", models.CharField(max_length=64, blank=True)),
                ("image", models.ImageField(upload_to="certificates/overlays/")),
                ("order", models.PositiveSmallIntegerField(default=0, db_index=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "certificate",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="overlay_images",
                        to="certificates.certificate",
                    ),
                ),
            ],
            options={
                "ordering": ["order", "created_at"],
            },
        ),
    ]
