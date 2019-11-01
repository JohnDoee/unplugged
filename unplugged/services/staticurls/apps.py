from django.apps import AppConfig as DjangoAppConfig


class AppConfig(DjangoAppConfig):
    name = "unplugged.services.staticurls"
    verbose_name = "StaticUrls Service"
    label = "services_staticurls"

    def ready(self):
        from .handler import StaticUrlsServicePlugin  # NOQA
