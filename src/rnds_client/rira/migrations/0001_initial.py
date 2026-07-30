from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []

    operations = [
        migrations.CreateModel(
            name="RNDSDocumentRecord",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("id_local", models.CharField(max_length=100, unique=True)),
                ("id_rnds", models.CharField(blank=True, max_length=200, null=True)),
                ("status", models.CharField(blank=True, max_length=30, null=True)),
                ("erro", models.TextField(blank=True, null=True)),
                ("enviado_em", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Registro RNDS",
                "verbose_name_plural": "Registros RNDS",
                "app_label": "rnds_rira",
            },
        ),
    ]
