from django.apps import AppConfig as DjangoAppConfig


class AppConfig(DjangoAppConfig):
    name = "unplugged.services.api"
    verbose_name = "API Service"
    label = "services_api"

    def ready(self):
        from .handler import APIServicePlugin  # NOQA
