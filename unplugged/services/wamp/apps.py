from django.apps import AppConfig as DjangoAppConfig


class AppConfig(DjangoAppConfig):
    name = "unplugged.services.wamp"
    verbose_name = "WAMP Service"
    label = "services_wamp"

    def ready(self):
        from .handler import WAMPServicePlugin  # NOQA
