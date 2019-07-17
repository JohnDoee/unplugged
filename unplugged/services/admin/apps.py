from django.apps import AppConfig as DjangoAppConfig


class AppConfig(DjangoAppConfig):
    name = "unplugged.services.admin"
    verbose_name = "Admin Service"
    label = "services_admin"

    def ready(self):
        from .handler import AdminService  # NOQA
