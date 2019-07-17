from django.conf import settings

from ..baseplugin import PluginBase


def pytest_configure():
    settings.configure(
        DATABASES={
            "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}
        },
        INSTALLED_APPS=[
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "unplugged",
        ],
    )

    class VehiclePlugin(PluginBase):
        pass
