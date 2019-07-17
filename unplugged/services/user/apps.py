from django.apps import AppConfig as DjangoAppConfig


class AppConfig(DjangoAppConfig):
    name = "unplugged.services.user"
    verbose_name = "User Service"
    label = "services_user"

    def ready(self):
        from .handler import UserServicePlugin  # NOQA
