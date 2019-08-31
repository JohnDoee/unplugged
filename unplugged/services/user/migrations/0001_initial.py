# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import jsonfield.fields
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="Userinfo",
            fields=[
                (
                    "id",
                    models.AutoField(
                        verbose_name="ID",
                        serialize=False,
                        auto_created=True,
                        primary_key=True,
                    ),
                ),
                ("key", models.CharField(max_length=50)),
                ("value", jsonfield.fields.JSONField(default=dict, blank=True)),
                (
                    "user",
                    models.ForeignKey(
                        to=settings.AUTH_USER_MODEL, on_delete=models.deletion.CASCADE
                    ),
                ),
            ],
        ),
        migrations.AlterUniqueTogether(
            name="userinfo", unique_together=set([("user", "key")])
        ),
    ]
