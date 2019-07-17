# Generated by Django 2.2 on 2019-04-25 13:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("unplugged", "0003_simpleadminplugin_display_name")]

    operations = [
        migrations.AlterField(
            model_name="simpleadminplugin",
            name="display_name",
            field=models.CharField(
                blank=True, help_text="Human readable name", max_length=200, null=True
            ),
        ),
        migrations.AlterField(
            model_name="simpleadminplugin",
            name="name",
            field=models.CharField(
                blank=True,
                help_text="Slugified name, used for actual name (and be able to find the plugin again)",
                max_length=200,
                null=True,
            ),
        ),
    ]
