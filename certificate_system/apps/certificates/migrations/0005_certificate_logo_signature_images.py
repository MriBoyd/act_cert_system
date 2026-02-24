from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("certificates", "0004_featureflagoverride"),
    ]

    operations = [
        migrations.AddField(
            model_name="certificate",
            name="logo_image",
            field=models.ImageField(blank=True, upload_to="certificates/overlays/"),
        ),
        migrations.AddField(
            model_name="certificate",
            name="signature_image",
            field=models.ImageField(blank=True, upload_to="certificates/overlays/"),
        ),
    ]
