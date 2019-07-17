# Generated by Django 2.2 on 2019-05-18 15:57

import django.db.models.deletion
import jsonfield.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("unplugged", "0004_auto_20190425_1302")]

    operations = [
        migrations.AlterField(
            model_name="simpleadminplugin",
            name="auto_created_plugins",
            field=models.ManyToManyField(
                blank=True, related_name="auto_created_plugins", to="unplugged.Plugin"
            ),
        ),
        migrations.AlterField(
            model_name="simpleadminplugin",
            name="config",
            field=jsonfield.fields.JSONField(blank=True, default=dict),
        ),
        migrations.CreateModel(
            name="Schedule",
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
                ("interval", models.IntegerField()),
                ("command", models.CharField(max_length=200)),
                ("kwargs", jsonfield.fields.JSONField()),
                ("enabled", models.BooleanField(default=False)),
                (
                    "plugin",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="unplugged.Plugin",
                    ),
                ),
            ],
        ),
    ]
