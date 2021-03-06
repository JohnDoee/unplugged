# Generated by Django 2.2.8 on 2020-04-02 14:07

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("services_admin", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="ExternalPlugin",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=150)),
                ("version", models.CharField(max_length=30)),
                ("description", models.TextField()),
                ("plugin_file", models.FileField(upload_to="externalplugins/")),
                ("created", models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
